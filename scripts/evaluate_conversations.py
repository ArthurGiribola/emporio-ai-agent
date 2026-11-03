"""Run a small real Ollama multi-turn evaluation against existing demo services."""
import argparse
import json
import os
import re
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


def evaluation_tool_event(event):
    """Keep synthetic evidence useful for diagnosis without customer/private fields."""
    name, result = event.get('name'), event.get('result', {})
    data = result.get('data', {}) if result.get('status') == 'ok' else {}
    arguments = event.get('effective_arguments', {})
    safe_args = {}
    for key in ('query', 'category_id', 'max_price_brl', 'sort_by', 'all_results', 'available_only',
                'product_id', 'payment_method', 'order_id'):
        if key in arguments and key != 'query' or key == 'query' and name in {'search_products', 'search_policies'}:
            value = arguments[key]
            safe_args[key] = value if isinstance(value, (str, int, float, bool)) or value is None else None
    safe = {'event': 'tool_result', 'tool': name, 'requested_arguments': safe_args,
            'effective_arguments': safe_args, 'status': result.get('status')}
    if result.get('status') == 'error':
        safe['error_code'] = result.get('error')
        return safe
    if name == 'search_products':
        safe['result'] = {'catalog_state': data.get('catalog_state'), 'total_matches': data.get('total_matches'),
            'returned_count': data.get('returned_count'), 'truncated': data.get('truncated'),
            'products': [{k: row.get(k) for k in ('product_id', 'name', 'category_id', 'list_price_brl',
                'effective_price_brl', 'available')} for row in data.get('products', [])]}
    elif name in {'get_product', 'get_price_quote'}:
        safe['result'] = {key: data.get(key) for key in ('product_id', 'name', 'category', 'available',
            'recorded_stock_quantity', 'base_price_brl', 'final_price_brl', 'payment_method',
            'discount_percent', 'discount_kind', 'warnings') if key in data}
    elif name == 'search_policies':
        safe['result'] = {'status': data.get('status'), 'references': data.get('references', [])}
        assessment = data.get('online_return_assessment')
        if isinstance(assessment, dict):
            safe['result']['online_return_assessment'] = {
                key: assessment.get(key) for key in
                ('channel', 'elapsed_days', 'window_days', 'within_window', 'eligibility_determined')}
    elif name == 'lookup_order':
        order = data.get('order') or {}
        safe['result'] = {'status': data.get('status'), 'order_status': order.get('status'),
            'total_brl': order.get('total_brl'), 'tracking_present': bool(order.get('tracking_code')),
            'items': [{'name': item.get('product_name'), 'quantity': item.get('quantity')}
                      for item in order.get('items', [])]}
    else:
        safe['result'] = {'status': data.get('status')}
    return safe


def evaluation_route_event(event):
    """Capture function names/arguments from synthetic evaluation turns only."""
    if event.get('event') != 'model_response':
        return summarize_event(event)
    calls = []
    allowed = {'search_products', 'get_product', 'get_price_quote', 'list_promotions', 'lookup_order', 'search_policies'}
    for call in event.get('calls', []):
        name = call.get('name')
        if name not in allowed:
            calls.append({'name': 'unknown', 'argument_keys': sorted(call.get('arguments', {}))})
            continue
        args = call.get('arguments', {})
        calls.append({'name': name, 'arguments': {key: value for key, value in args.items()
            if key in {'query', 'category_id', 'max_price_brl', 'sort_by', 'all_results',
                       'available_only', 'product_id', 'payment_method', 'order_id'}
            and isinstance(value, (str, int, float, bool))}})
    result = summarize_event(event)
    result['calls'] = calls
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenarios', type=Path, default=ROOT / 'scripts' / 'conversation_scenarios.json')
    parser.add_argument('--suite', choices=('smoke', 'primary', 'variety', 'all'), default='smoke',
                        help='Named subset of the shared scenario dataset (default: smoke).')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports' / 'latest.json')
    parser.add_argument('--model', default='qwen3:4b-instruct')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset = json.loads(args.scenarios.read_text(encoding='utf-8'))
    scenarios = [scenario for scenario in dataset['scenarios']
                 if args.suite == 'all' or scenario.get('suite', 'smoke') == args.suite]
    if not scenarios:
        parser.error(f"No scenarios found for suite '{args.suite}' in {args.scenarios}")
    env = {'EMPORIO_DATA_MODE': 'demo', 'OLLAMA_MODEL': args.model,
           'OLLAMA_BASE_URL': os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')}
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'model': args.model,
              'suite': args.suite,
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
        for scenario in scenarios:
            session.reset()
            turns, scenario_pass = [], True
            for case in scenario['turns']:
                events = []
                previous = session._agent._observer
                def observe(event):
                    previous(event)
                    events.append(event)
                session._agent._observer = observe
                start = time.perf_counter()
                answer = session.ask(case['user'])
                latency_ms = round((time.perf_counter() - start) * 1000)
                session._agent._observer = previous
                tools = [event['name'] for event in events if event.get('event') == 'tool_result']
                status = next((e.get('status') for e in reversed(events) if e.get('event') == 'turn_failure'), 'answered')
                scope = next((e.get('status') for e in reversed(events) if e.get('event') == 'scope_decision'), None)
                if scope in {'outside', 'uncertain'} and status == 'answered':
                    status = 'out_of_scope' if scope == 'outside' else 'scope_uncertain'
                visible_text = answer.text
                catalog_products = []
                if answer.catalog is not None:
                    catalog_products = [{'name': entry.name, 'price_brl': str(entry.price_brl),
                                         'available': entry.available} for entry in answer.catalog.entries]
                    visible_text += '\n' + '\n'.join(p['name'] for p in catalog_products)
                expected_status = case.get('expected_status')
                if expected_status is None:
                    expected_status = {'outside': 'out_of_scope', 'uncertain': 'scope_uncertain'}.get(case.get('expected_scope'), 'answered')
                required_tool = case.get('must_call_tool')
                accepted_tools = case.get('must_call_any', [])
                checks = {
                    'status': status == expected_status,
                    'scope': scope == case['expected_scope'] if case.get('expected_scope') else True,
                    'tool_required': (required_tool in tools if required_tool else
                                      any(tool in tools for tool in accepted_tools) if accepted_tools else True),
                    'no_tools': not tools if case.get('must_not_call_tools') else True,
                    'answer_content': all(term.casefold() in visible_text.casefold() for term in case.get('must_include_all', [])) and
                        (any(term.casefold() in visible_text.casefold() for term in case['must_include_any']) if case.get('must_include_any') else True),
                    'forbidden_claims': not any(term.casefold() in visible_text.casefold() for term in case.get('must_not_include', [])),
                    'no_purchase_claim': not case.get('must_not_claim_purchase') or not any(
                        term in answer.text.casefold() for term in ('pedido criado', 'compra realizada', 'order created')),
                    'no_internal_jargon': not re.search(
                        r'\b(?:snapshot|list_price_brl|tool_call|tool call|data retrieval|database field|'
                        r'retrieval system|function calling)\b', visible_text, re.IGNORECASE),
                }
                expected_policy_assessment = case.get('expected_policy_assessment')
                if expected_policy_assessment:
                    evidence = next((event.get('result', {}).get('data', {}).get('online_return_assessment')
                                     for event in reversed(events)
                                     if event.get('event') == 'tool_result' and event.get('name') == 'search_policies'
                                     and event.get('result', {}).get('status') == 'ok'), None)
                    checks['policy_assessment'] = bool(evidence) and all(
                        evidence.get(key) == value for key, value in expected_policy_assessment.items())
                if case.get('max_answer_words') is not None:
                    checks['concise'] = len(re.findall(r'\b[\w-]+\b', answer.text)) <= case['max_answer_words']
                expected_safe_tool_error = expected_status == 'tool_error' and status == 'tool_error'
                passed = all(checks.values()) and (not answer.error or expected_safe_tool_error)
                scenario_pass &= passed
                turns.append({'user': case['user'],
                              'answer': answer.text if not case.get('must_redact_answer') else None,
                              'answer_redacted': bool(case.get('must_redact_answer')), 'status': status,
                              'error': answer.error, 'latency_ms': latency_ms,
                              'catalog_products': catalog_products,
                              'tool_events': [evaluation_tool_event(e) for e in events if e.get('event') == 'tool_result'],
                              'routing_events': [evaluation_route_event(e) for e in events if e.get('phase') == 'scope' or e.get('event') in {'scope_decision', 'model_response'}],
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
