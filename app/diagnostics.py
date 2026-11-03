"""Opt-in developer events with no questions, IDs, policy text or tool bodies."""

import json
import sys

TOOLS = {'search_products', 'get_product', 'get_price_quote', 'list_promotions', 'lookup_order', 'search_policies'}
CODES = {'provider_error', 'connection_error', 'timeout', 'invalid_json', 'invalid_response', 'output_limit',
         'response_too_large', 'rate_limit', 'http_error', 'invalid_tool_calls', 'invalid_arguments',
         'ambiguous_product_reference', 'product_not_found', 'pricing_conflict', 'tool_failure', 'tool_error',
         'context_limit', 'limit_reached', 'unverified', 'answered', 'ok', 'error', 'internal_error', 'result_too_large', 'unknown_tool', 'shop', 'outside', 'uncertain'}


def summarize_event(event):
    safe = {'event': event.get('event', 'unknown')}
    for key in ('tool_count', 'guarded'):
        if key in event and isinstance(event[key], (int, bool)):
            safe[key] = event[key]
    for key in ('status', 'reason'):
        if key in event:
            safe[key] = event[key] if event[key] in CODES else 'unknown'
    if event.get('phase') in {'scope', 'business', 'tool', 'orchestration'}:
        safe['phase'] = event['phase']
    if event.get('exception_type') in {'RuntimeError','ValueError','TypeError','KeyError','OSError','IndexError','AttributeError'}:
        safe['exception_type'] = event['exception_type']
    if event.get('event') == 'model_response':
        safe['call_count'] = len(event.get('calls', ()))
        safe['has_text'] = bool(event.get('text'))
    if event.get('event') == 'tool_result':
        safe['tool'] = event['name'] if event['name'] in TOOLS else 'unknown'
        safe['status'] = event['result'].get('status')
        error = event['result'].get('error')
        safe['error_code'] = error if error in CODES else 'unknown' if error else None
        arguments = event.get('effective_arguments')
        safe['argument_count'] = len(arguments) if isinstance(arguments, dict) else 0
    return safe


def developer_observer(enabled=False):
    def observe(event):
        if enabled:
            print(json.dumps(summarize_event(event), ensure_ascii=True), file=sys.stderr, flush=True)
    return observe
