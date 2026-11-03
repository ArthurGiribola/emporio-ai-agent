"""Multi-turn TASK-COMPLETION evaluation on the fictional 65-product catalog.

Runs the real ChatSession (LOCAL-shaped, fictional data) end to end and checks
OUTCOMES, separated by dimension:

  task         - every expectation of every turn of a scenario holds
  factual      - every price, stock count, product count, product name and
                 order fact in the visible answer agrees with the deterministic
                 services; no purchase/reservation is claimed
  tools        - expected tool/product was consulted; forbidden tools were not
  continuity   - references (positions, "esse", selection) resolved to the
                 right product
  clarify      - asked a question when one was required
  conversation - no internal failure text, no repeated product card
  latency      - wall time and LLM calls per turn

Model modes:
  --model qwen3:4b-instruct   real local Ollama (the measurement that matters)
  --stub oracle               scripted cooperative model: does what an ideal
                              model would do, only with the tools it is offered
  --stub text                 model that never calls tools (conversation checks)

Scenario expectations are frozen: change them only to fix a demonstrably wrong
expectation, never to make a run pass.
"""

import argparse
import json
import re
import statistics
import sys
import tempfile
import time
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.providers import create_provider  # noqa: E402
from app.web_session import ChatSession  # noqa: E402
from tests.task_fixtures import write_catalog65  # noqa: E402

SCENARIOS = ROOT / "scripts" / "task_scenarios.json"
FAILURE_TEXT = re.compile(
    r"não consegui confirmar os dados|o modelo não concluiu|o modelo local|uma falha de processamento|"
    r"a consulta falhou|consulta inválida|pode esclarecer como sua pergunta se relaciona|fora do escopo|"
    r"excede o contexto", re.I)
PURCHASE_CLAIM = re.compile(
    r"\b(?:compra|pedido)\s+(?:foi\s+)?(?:finalizad[ao]|realizad[ao]|conclu[ií]d[ao]|confirmad[ao]|criad[ao]|efetuad[ao])\b|"
    r"\b(?:reservei|separei|finalizei|registrei (?:a|o) (?:compra|pedido))\b", re.I)
MONEY = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})")
STOCK = re.compile(r"\b(\d+)\s+unidades?\b", re.I)
COUNT = re.compile(r"\b(\d+)\s+(?:produtos|opções|instrumentos|itens|modelos)\b", re.I)


def _money(text):
    return Decimal(text.replace(".", "").replace(",", "."))


# ----------------------------------------------------------------- model stubs
class Oracle:
    """Holds the scripted behaviour for the current turn."""

    def __init__(self, mode):
        self.mode, self.turn, self.resolve = mode, {}, None

    def transport(self, url, payload, headers, timeout):
        if url.endswith("/api/show"):
            return {"capabilities": ["tools"]}
        offered = [t["function"]["name"] for t in payload.get("tools", [])]
        if offered[:1] == ["check_shop_scope"]:
            call = {"function": {"name": "check_shop_scope", "arguments": {"decision": "shop", "language": "pt"}}}
            return {"done": True, "message": {"role": "assistant", "content": "", "tool_calls": [call]}}
        text = self.turn.get("text", "Certo! Como posso ajudar?")
        if self.mode == "text" or payload["messages"][-1]["role"] == "tool" or not offered:
            return {"done": True, "message": {"role": "assistant", "content": text}}
        wanted = [c for c in self.turn.get("calls", []) if c["name"] in offered]
        if not wanted:
            if not self.turn.get("calls"):
                return {"done": True, "message": {"role": "assistant", "content": text}}
            wanted = [{"name": offered[0], "arguments": {}}]  # cooperative: use what is offered
        calls = [{"function": {"name": c["name"], "arguments": self.resolve(c.get("arguments", {}))}} for c in wanted]
        return {"done": True, "message": {"role": "assistant", "content": "", "tool_calls": calls}}


# ----------------------------------------------------------------- harness
@contextmanager
def fixture_environment():
    with tempfile.TemporaryDirectory(prefix="emporio-task65-") as directory:
        policy = write_catalog65(Path(directory))
        yield {"EMPORIO_DATA_MODE": "local", "EMPORIO_DATA_DIR": directory, "EMPORIO_POLICY_PATH": str(policy),
               "EMPORIO_ENABLE_DEMO_IDENTITY": "1", "EMPORIO_DEMO_CUSTOMER_ID": "1", "EMPORIO_ORDER_ID": "1"}


class SelectionImpossible(Exception):
    """The customer could not click item N: no such item was ever displayed."""


class Run:
    def __init__(self, env, model=None, stub=None):
        self.oracle = Oracle(stub) if stub else None
        factory = (lambda config: create_provider(config, self.oracle.transport)) if stub else create_provider
        env = dict(env, OLLAMA_MODEL=model or "qwen3:4b-instruct")
        self.session = ChatSession(provider_factory=factory, environment=env)
        self.catalog = self.session._tools._catalog
        self.events = []
        previous = self.session._agent._observer
        self.session._agent._observer = lambda e: (previous(e), self.events.append(e))
        self.displayed = ()      # product ids of the last non-empty list the customer SAW
        self.selected = None     # product the customer clicked in the UI
        self.seen_ids = set()    # products whose facts were shown earlier in the scenario
        self.previous_answer = ""
        if self.oracle:
            self.oracle.resolve = self.resolve_arguments

    def ref(self, value):
        if value == "$selected":
            return self.selected
        if isinstance(value, str) and value.startswith("$pos:"):
            position = int(value[5:])
            return self.displayed[position - 1] if len(self.displayed) >= position else None
        if isinstance(value, str) and value.startswith("$name:"):
            name = value[6:]
            return next(p.product_id for p in self.catalog.repository.products.values() if p.name == name)
        return value

    def resolve_arguments(self, arguments):
        return {k: self.ref(v) for k, v in arguments.items()}

    def name(self, ref):
        pid = self.ref(ref)
        return self.catalog.get_product(pid).name if pid else None

    def text_with_refs(self, text):
        return re.sub(r"\{(\$[^}]+)\}", lambda m: self.name(m[1]) or m[0], text)

    # ------------------------------------------------------------- evidence
    def evidence(self, events, answer):
        ids, totals = set(), set()
        prices, stocks, order_facts = set(), set(), set()
        for e in events:
            if e.get("event") != "tool_result" or e.get("result", {}).get("status") != "ok":
                continue
            data = e["result"]["data"]
            if e["name"] == "search_products":
                totals |= {data.get("total_matches"), data.get("returned_count")}
                ids |= {row["product_id"] for row in data.get("products", [])}
            elif e["name"] in {"get_product", "get_price_quote"}:
                ids.add(data["product_id"])
            elif e["name"] == "lookup_order" and data.get("order"):
                order = data["order"]
                prices.add(Decimal(str(order["total_brl"])))
                ids |= {item["product_id"] for item in order.get("items", []) if "product_id" in item}
                order_facts.add(order["status"])
            elif e["name"] == "list_promotions":
                ids |= {p["product_id"] for p in data.get("promotions", [])}
        if answer.catalog is not None:
            ids |= {entry.product_id for entry in answer.catalog.entries}
            totals |= {answer.catalog.total_matches, len(answer.catalog.entries)}
        for pid in ids:
            product = self.catalog.get_product(pid)
            stocks.add(product.stock_quantity)
            prices.add(product.price_brl)
            for method in ("list", "pix"):
                try:
                    prices.add(self.catalog.get_price_quote(pid, payment_method=method).final_price_brl)
                except Exception:
                    pass
        return ids, totals, prices, stocks

    def factual_problems(self, question, answer, events):
        text = answer.text
        ids, totals, prices, stocks = self.evidence(events, answer)
        user_numbers = {int(n) for n in re.findall(r"\d+", question)}
        words = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "tres": 3, "quatro": 4, "cinco": 5}
        user_numbers |= {v for k, v in words.items() if re.search(rf"\b{k}\b", question, re.I)}
        problems = []
        for raw in MONEY.findall(text):
            if _money(raw) not in prices:
                problems.append(f"price R$ {raw} not backed by service evidence")
        allowed_stock = stocks | user_numbers | {s - q for s in stocks for q in user_numbers if s is not None}
        for raw in STOCK.findall(text):
            if int(raw) not in allowed_stock:
                problems.append(f"stock/quantity {raw} not backed by evidence")
        for raw in COUNT.findall(text):
            if int(raw) not in totals and int(raw) not in user_numbers:
                problems.append(f"count {raw} not backed by search evidence")
        verified = ids | self.seen_ids | ({self.selected} if self.selected else set())
        for product in self.catalog.repository.products.values():
            if product.name in text and product.product_id not in verified:
                problems.append(f"product '{product.name}' mentioned without evidence")
        if PURCHASE_CLAIM.search(text):
            problems.append("claims a purchase/order/reservation was made")
        return problems, ids

    # ------------------------------------------------------------- one turn
    def turn(self, spec):
        user = spec["user"]
        if user.startswith("@select "):
            position = int(user.split()[1])
            if len(self.displayed) < position:
                raise SelectionImpossible(position)
            self.selected = self.displayed[position - 1]
            self.session.select_product(self.selected)
            return None
        question = self.text_with_refs(user)
        if self.oracle:
            self.oracle.turn = spec.get("oracle", {})
        self.events.clear()
        start = time.perf_counter()
        answer = self.session.ask(question)
        seconds = time.perf_counter() - start
        events = list(self.events)
        expect = spec.get("expect", {})
        checks = {}
        dims = {}

        def check(dimension, name, ok, detail=""):
            checks[name] = {"ok": bool(ok), "dimension": dimension, **({"detail": detail} if not ok and detail else {})}

        problems, evidence_ids = self.factual_problems(question, answer, events)
        check("factual", "facts_backed_by_services", not problems, "; ".join(problems))
        check("conversation", "no_internal_failure", not FAILURE_TEXT.search(answer.text) and not answer.error,
              answer.text[:160])
        tool_events = [e for e in events if e.get("event") == "tool_result"]
        tools = [e["name"] for e in tool_events]
        looked_up = {e["result"]["data"].get("product_id") for e in tool_events
                     if e["name"] in {"get_product", "get_price_quote"} and e["result"].get("status") == "ok"}

        if "catalog" in expect:
            products = self.catalog.repository.products.values()
            want = expect["catalog"]
            if isinstance(want, dict):
                want_ids = {p.product_id for p in products
                            if (not want.get("category") or self.catalog.repository.categories[p.category_id].name == want["category"])
                            and (not want.get("brand") or p.name.split()[0] == want["brand"])
                            and (want.get("include_unavailable") or p.available)
                            and (not want.get("max_price") or p.price_brl <= Decimal(str(want["max_price"])))}
            else:
                want_ids = {p.product_id for p in products if want == "all" or p.available}
            got = {e.product_id for e in answer.catalog.entries} if answer.catalog else set()
            check("tools", "catalog_matches_request", got == want_ids,
                  f"expected {len(want_ids)} products, customer saw {len(got)}")
            for raw in COUNT.findall(answer.text):
                if int(raw) != len(want_ids):
                    check("factual", "stated_count_is_total", False, f"text says {raw}, catalog has {len(want_ids)}")
        for key in ("shows_product", "consults_product"):
            if key in expect:
                pid = self.ref(expect[key])
                name = self.catalog.get_product(pid).name if pid else "?"
                dimension = "continuity" if str(expect[key]).startswith(("$pos", "$selected")) else "tools"
                ok = (name in answer.text) if key == "shows_product" else (pid in looked_up)
                check(dimension, key, ok and pid is not None, f"expected {name}")
        if "consults_products" in expect:
            pids = {self.ref(r) for r in expect["consults_products"]}
            check("continuity", "consults_products", pids <= (looked_up | evidence_ids), f"expected {sorted(map(str, pids))}")
        if expect.get("asks_question"):
            check("clarify", "asks_question", "?" in answer.text, answer.text[:160])
        if expect.get("asks_quantity"):
            check("clarify", "asks_quantity", "?" in answer.text and re.search(r"quant[ao]s|quantidade", answer.text, re.I),
                  answer.text[:160])
        if "mentions" in expect:
            for fragment in expect["mentions"]:
                check("conversation", f"mentions:{fragment}", re.search(fragment, answer.text, re.I), answer.text[:160])
        if expect.get("no_tools"):
            check("tools", "no_tools", not tools, str(tools))
        for name in expect.get("forbid_tools", []):
            check("tools", f"not:{name}", name not in tools, str(tools))
        if expect.get("no_catalog_search"):
            check("tools", "no_catalog_search", "search_products" not in tools and answer.catalog is None, str(tools))
        if expect.get("not_specific_product"):
            check("clarify", "does_not_guess", len(looked_up) != 1, f"guessed {looked_up}")
        if expect.get("no_repeat_card") and self.previous_answer:
            previous_lines = {l.strip() for l in self.previous_answer.splitlines() if len(l.strip()) > 40}
            repeated = [l for l in answer.text.splitlines() if l.strip() in previous_lines]
            check("conversation", "no_repeated_card", not repeated, repeated[0][:120] if repeated else "")
        if expect.get("grammatical_quantity"):
            check("conversation", "grammatical_quantity", not re.search(r"\b(?:as|os) 1 \w+s\b|\bsobraria \d+(?!\s+unidade)", answer.text),
                  answer.text[:200])

        if answer.catalog is not None and answer.catalog.entries:
            self.displayed = tuple(e.product_id for e in answer.catalog.entries)
        self.seen_ids |= evidence_ids
        self.previous_answer = answer.text
        passed = all(c["ok"] for c in checks.values())
        return {"user": question, "answer": answer.text, "passed": passed, "checks": checks, "tools": tools,
                "catalog_entries": len(answer.catalog.entries) if answer.catalog else None,
                "seconds": round(seconds, 3), "llm_calls": sum(e.get("event") == "model_response" for e in events)}


def run_scenarios(scenarios, *, model=None, stub=None):
    results = []
    with fixture_environment() as env:
        for scenario in scenarios:
            run = Run(env, model=model, stub=stub)
            turns = []
            try:
                for spec in scenario["turns"]:
                    result = run.turn(spec)
                    if result is not None:
                        turns.append(result)
            except SelectionImpossible as error:
                turns.append({"user": f"@select {error.args[0]}", "answer": "", "passed": False, "tools": [],
                              "catalog_entries": None, "seconds": 0.0, "llm_calls": 0,
                              "checks": {"list_available_for_selection": {
                                  "ok": False, "dimension": "continuity",
                                  "detail": "no displayed list to select from; scenario aborted"}}})
            finally:
                run.session.close()
            results.append({"id": scenario["id"], "set": scenario["set"], "intent": scenario["intent"],
                            "passed": all(t["passed"] for t in turns), "turns": turns})
    return results


def summarize(results):
    turns = [t for r in results for t in r["turns"]]
    dims = {}
    for t in turns:
        for check in t["checks"].values():
            d = dims.setdefault(check["dimension"], [0, 0])
            d[0] += check["ok"]
            d[1] += 1
    latency = [t["seconds"] for t in turns]
    return {
        "task_completion": {"passed": sum(r["passed"] for r in results), "total": len(results)},
        "turns": {"passed": sum(t["passed"] for t in turns), "total": len(turns)},
        "checks_by_dimension": {k: {"passed": v[0], "total": v[1]} for k, v in sorted(dims.items())},
        "latency_seconds": {"mean": round(statistics.mean(latency), 3) if latency else 0,
                            "p50": round(statistics.median(latency), 3) if latency else 0,
                            "p95": round(sorted(latency)[int(0.95 * (len(latency) - 1))], 3) if latency else 0,
                            "max": round(max(latency), 3) if latency else 0},
        "llm_calls_per_turn": round(statistics.mean(t["llm_calls"] for t in turns), 2) if turns else 0,
        "by_intent": {i: {"passed": sum(r["passed"] for r in results if r["intent"] == i),
                          "total": sum(r["intent"] == i for r in results)} for i in sorted({r["intent"] for r in results})},
    }


def load(selection="all"):
    data = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    return [s for s in data["scenarios"] if selection == "all" or s["set"] == selection]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", choices=("dev", "holdout", "all"), default="all")
    parser.add_argument("--model", default="qwen3:4b-instruct")
    parser.add_argument("--stub", choices=("oracle", "text"))
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "task-eval-latest.json")
    args = parser.parse_args()
    results = run_scenarios(load(args.set), model=args.model, stub=args.stub)
    report = {"model": None if args.stub else args.model, "stub": args.stub, "set": args.set,
              "data": "fictional 65-product catalog (tests/task_fixtures.py)",
              "summary": summarize(results), "scenarios": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    s = report["summary"]
    print(f"Task completion: {s['task_completion']['passed']}/{s['task_completion']['total']} scenarios; "
          f"turns {s['turns']['passed']}/{s['turns']['total']}")
    for name, value in s["checks_by_dimension"].items():
        print(f"  {name:13} {value['passed']}/{value['total']}")
    print(f"  latency p50 {s['latency_seconds']['p50']}s p95 {s['latency_seconds']['p95']}s; "
          f"{s['llm_calls_per_turn']} LLM calls/turn")
    for r in results:
        for t in r["turns"]:
            if not t["passed"]:
                bad = [k for k, c in t["checks"].items() if not c["ok"]]
                print(f"  FAIL {r['id']}: {t['user'][:60]!r} -> {bad}")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
