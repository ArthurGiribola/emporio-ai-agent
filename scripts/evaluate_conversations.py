"""Run a small real Ollama multi-turn evaluation against existing demo services."""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.diagnostics import summarize_event
from app.web_session import ChatSession


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenarios', type=Path, default=ROOT / 'scripts' / 'conversation_eval_seed.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'conversation-eval-report.json')
    parser.add_argument('--model', default='qwen3:4b-instruct')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset = json.loads(args.scenarios.read_text(encoding='utf-8'))
    env = {'EMPORIO_DATA_MODE': 'demo', 'OLLAMA_MODEL': args.model,
           'OLLAMA_BASE_URL': os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')}
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'model': args.model,
              'data_mode': 'DEMO synthetic fixtures', 'source_data_included': False,
              'scenarios': []}
    try:
        endpoint = urlsplit(env['OLLAMA_BASE_URL'])
        connection = HTTPConnection(endpoint.hostname, endpoint.port or 80, timeout=2)
        connection.request('GET', '/api/tags')
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError('ollama_unavailable')
        installed = [m.get('name', '').split(':')[0] for m in json.loads(response.read()).get('models', [])]
        connection.close()
        if args.model.split(':')[0] not in installed:
            raise RuntimeError('requested_model_not_installed')
        session = ChatSession(environment=env)
    except Exception as error:
        reason = str(error) if str(error) in {'requested_model_not_installed', 'ollama_unavailable'} else 'ollama_unavailable' if isinstance(error, (TimeoutError, OSError, ConnectionError)) else type(error).__name__
        report.update(fatal_error=reason, overall={'passed': 0, 'total': 0})
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"Could not initialize local evaluation ({type(error).__name__}). Report: {args.output}")
        return 2

    try:
        for scenario in dataset['scenarios']:
            session.reset()
            turns, scenario_pass = [], True
            for case in scenario['turns']:
                events = []
                previous = session._agent._observer
                def observe(event):
                    previous(event)
                    events.append(summarize_event(event))
                session._agent._observer = observe
                start = time.perf_counter()
                answer = session.ask(case['user'])
                latency_ms = round((time.perf_counter() - start) * 1000)
                session._agent._observer = previous
                tools = [event['tool'] for event in events if event.get('event') == 'tool_result']
                status = next((e.get('status') for e in reversed(events) if e.get('event') == 'turn_failure'), 'answered')
                visible_text = answer.text
                catalog_products = []
                if answer.catalog is not None:
                    catalog_products = [{'name': entry.name, 'price_brl': str(entry.price_brl),
                                         'available': entry.available} for entry in answer.catalog.entries]
                    visible_text += '\n' + '\n'.join(p['name'] for p in catalog_products)
                checks = {
                    'status': status == case.get('expected_status'),
                    'tool_required': case.get('must_call_tool') in tools if case.get('must_call_tool') else True,
                    'no_tools': not tools if case.get('must_not_call_tools') else True,
                    'answer_content': all(term.casefold() in visible_text.casefold() for term in case.get('must_include_all', [])) and
                        (any(term.casefold() in visible_text.casefold() for term in case['must_include_any']) if case.get('must_include_any') else True),
                    'forbidden_claims': not any(term.casefold() in visible_text.casefold() for term in case.get('must_not_include', [])),
                    'no_purchase_claim': not case.get('must_not_claim_purchase') or not any(
                        term in answer.text.casefold() for term in ('pedido criado', 'compra realizada', 'order created')),
                }
                passed = all(checks.values()) and not answer.error
                scenario_pass &= passed
                turns.append({'user': case['user'],
                              'answer': answer.text if not case.get('must_redact_answer') else None,
                              'answer_redacted': bool(case.get('must_redact_answer')), 'status': status,
                              'error': answer.error, 'latency_ms': latency_ms,
                              'catalog_products': catalog_products,
                              'tool_events': [e for e in events if e.get('event') == 'tool_result'],
                              'routing_events': [e for e in events if e.get('phase') == 'scope' or e.get('event') == 'scope_decision'],
                              'checks': checks, 'passed': passed})
            report['scenarios'].append({'id': scenario['id'], 'category': scenario['category'],
                                        'passed': scenario_pass, 'turns': turns})
    finally:
        session.close()

    flat = [t for s in report['scenarios'] for t in s['turns']]
    report['overall'] = {'passed': sum(t['passed'] for t in flat), 'total': len(flat),
                         'pass_rate': round(sum(t['passed'] for t in flat) / len(flat), 3) if flat else 0,
                         'mean_latency_ms': round(sum(t['latency_ms'] for t in flat) / len(flat)) if flat else 0}
    report['categories'] = {category: {'passed': sum(t['passed'] for s in report['scenarios'] if s['category'] == category for t in s['turns']),
                                       'total': sum(len(s['turns']) for s in report['scenarios'] if s['category'] == category)}
                            for category in sorted({s['category'] for s in report['scenarios']})}
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Evaluation: {report['overall']['passed']}/{report['overall']['total']} turns passed; "
          f"mean latency {report['overall']['mean_latency_ms']} ms. Report: {args.output}")
    for category, result in report['categories'].items():
        print(f"  {category}: {result['passed']}/{result['total']}")
    failures = [(scenario['id'], turn['user'], turn['status']) for scenario in report['scenarios']
                for turn in scenario['turns'] if not turn['passed']]
    for scenario_id, question, status in failures:
        print(f"  FAIL {scenario_id} [{status}]: {question}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
