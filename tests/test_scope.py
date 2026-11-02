"""Real scope orchestration with mocked model replies; live checks are separate."""
import copy
import json
import unittest
from unittest.mock import Mock, patch
from app.agent import Agent, AgentResult
from app.providers import ProviderReply, ToolCall, ProviderError
from app.scope import assess_scope
from app.synthetic import SyntheticTools
from app.web_session import ChatSession


def decision(value="shop", language="en"):
    return ProviderReply("", (ToolCall("check_shop_scope", {"decision":value,"language":language}),), {})


def quote():
    return ProviderReply("", (ToolCall("get_price_quote", {"product_id":1,"payment_method":"pix"}),), {})


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.tools=SyntheticTools()
        self.addCleanup(self.tools.close)

    def agent(self,replies):
        provider=Mock(external=False)
        provider.complete.side_effect=replies
        return Agent(provider,self.tools),provider

    def test_unrelated_initial_questions_redirect_without_business_calls(self):
        for question,lang in [("What is the capital of France?","en"),("Qual é a capital da França?","pt"),
                              ("Tell me tomorrow's sports scores.","en")]:
            agent,provider=self.agent([decision("outside",lang)])
            result=agent.run(question)
            self.assertEqual(result.status,"out_of_scope")
            self.assertIn("Empório da Música",result.text)
            self.assertEqual(provider.complete.call_count,1)
            self.assertEqual(result.tools_called,())
            self.assertEqual(agent._turns,[])

    def test_prior_tools_do_not_authorize_general_answers_or_pollute_followups(self):
        agent,provider=self.agent([decision(),quote(),ProviderReply("quote",(),{}),
            decision("outside"),decision("outside","pt"),decision(),quote(),ProviderReply("Yes, the recorded promotional price is 90.09.",(),{})])
        self.assertEqual(agent.run("What is the PIX price for product ID 1?").status,"answered")
        previous=copy.deepcopy(agent._turns)
        self.assertEqual(agent.run("What is the capital of France?").status,"out_of_scope")
        self.assertEqual(agent.run("Escreva um algoritmo de ordenação.").status,"out_of_scope")
        self.assertEqual(agent._turns,previous)
        result=agent.run("Does that include the promotional discount?")
        self.assertEqual(result.status,"answered")
        self.assertIn("90.09",result.text)
        history=json.dumps(provider.complete.call_args.args[0])
        self.assertNotIn("France",history)
        self.assertNotIn("ordena",history)

    def test_programming_and_mixed_requests_cannot_use_a_shop_word_as_permission(self):
        for q in ["Write bubble sort code.","Generate a web server for my guitar store.",
                  "Check a guitar price and then do my unrelated coding homework."]:
            agent,provider=self.agent([decision("outside")])
            self.assertEqual(agent.run(q).status,"out_of_scope")
            self.assertEqual(provider.complete.call_count,1)

    def test_legitimate_scope_decisions_reach_existing_tools(self):
        cases=[("Compare nylon and steel-string instruments.","get_product",{"product_id":1}),
               ("Qual a garantia do meu instrumento?","search_policies",{"query":"garantia"}),
               ("Do you stock a Moog Subsequent 37?","search_products",{"query":"Moog"}),
               ("How do I connect a MIDI keyboard?","get_product",{"product_id":1}),
               ("What are your opening hours?","search_policies",{"query":"horario"}),
               ("Qual é o status do pedido 1?","lookup_order",{"order_id":1})]
        for q,tool,arguments in cases:
            agent,provider=self.agent([decision(),ProviderReply("",(ToolCall(tool,arguments),),{}),ProviderReply("source",(),{})])
            result=agent.run(q)
            self.assertEqual(result.status,"answered",q)
            self.assertIn(tool,result.tools_called)
            self.assertEqual(provider.complete.call_count,3)

    def test_missing_malformed_or_multiple_decisions_fail_closed(self):
        bad=[ProviderReply("shop",(),{}),ProviderReply("",(ToolCall("lookup_order",{"order_id":1}),),{}),
             ProviderReply("",(ToolCall("check_shop_scope",{"decision":[],"language":"en"}),),{}),
             ProviderReply("",(ToolCall("check_shop_scope",{"decision":"shop","language":"en","identity":2}),),{}),
             ProviderReply("",decision().calls*2,{})]
        for reply in bad:
            agent,provider=self.agent([reply])
            self.assertEqual(agent.run("Please help with a guitar.").status,"scope_uncertain")
            self.assertEqual(provider.complete.call_count,1)
            self.assertFalse(agent._turns)

    def test_current_language_overrides_stale_model_language(self):
        agent,_=self.agent([decision("outside","en")])
        self.assertTrue(agent.run("Escreva um programa de ordenação.").text.startswith("Posso ajudar"))
        agent,_=self.agent([decision("outside","pt")])
        self.assertTrue(agent.run("Write unrelated code.").text.startswith("I can help"))

    def test_history_words_do_not_override_an_explicit_outside_decision(self):
        agent,_=self.agent([decision('outside')])
        answer=agent.run('Where is the capital of France? Remember our conversation history.')
        self.assertEqual(answer.status,'out_of_scope')

    def test_scope_network_failure_does_not_fall_through(self):
        agent,provider=self.agent([ProviderError("Connection failed")])
        self.assertEqual(agent.run("What is a guitar price?").status,"provider_error")
        self.assertEqual(provider.complete.call_count,1)

    def test_business_request_limit_plus_one_bounded_scope_call(self):
        provider=Mock(external=False,complete=Mock(side_effect=[decision(),quote()]))
        result=Agent(provider,self.tools,max_requests=1).run("What is the PIX price for product ID 1?")
        self.assertEqual(result.status,"limit_reached")
        self.assertEqual(provider.complete.call_count,2)

    def test_cloud_projection_precedes_scope_and_drops_raw_unknown_text(self):
        provider=Mock(external=True)
        provider.complete.side_effect=[decision(),quote(),ProviderReply("quote",(),{})]
        agent=Agent(provider,self.tools)
        result=agent.run("preco produto ID 1 pix UnknownPrivateCanary")
        self.assertEqual(result.status,"answered")
        for call in provider.complete.call_args_list:
            self.assertNotIn("UnknownPrivateCanary",json.dumps(call.args))
        provider.complete.reset_mock()
        self.assertEqual(agent.run("email private@example.invalid").status,"privacy_blocked")
        provider.complete.assert_not_called()

    def test_web_displays_safe_redirect_as_normal_answer(self):
        session=ChatSession(provider_factory=lambda config:Mock(external=False),environment={})
        self.addCleanup(session.close)
        with patch.object(session._agent,"run",return_value=AgentResult("out_of_scope","Safe store redirect")):
            answer=session.ask("unrelated")
            self.assertFalse(answer.error)
            self.assertEqual(answer.text,"Safe store redirect")


@unittest.skipUnless(__import__("os").environ.get("EMPORIO_RUN_LIVE")=="1", "Live scope checks disabled; set EMPORIO_RUN_LIVE=1")
class LiveScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import socket
        try:
            with socket.create_connection(("127.0.0.1",11434),timeout=1): pass
        except OSError:
            raise unittest.SkipTest("Local Ollama unavailable")

    def provider(self):
        import os
        from app.providers import ProviderConfig,create_provider
        return create_provider(ProviderConfig(provider="ollama",model=os.environ.get("OLLAMA_MODEL","qwen3:4b-instruct"),timeout_seconds=120,max_output_tokens=2048))

    def test_actual_multiturn_scope_and_recovery(self):
        with SyntheticTools() as tools:
            agent=Agent(self.provider(),tools)
            first=agent.run("Please list all available products.")
            self.assertEqual(first.status,"answered",first.text)
            previous=copy.deepcopy(agent._turns)
            for q in ["What is the capital of France?","Write bubble sort code.","Escreva um algoritmo de ordenação."]:
                result=agent.run(q)
                self.assertIn(result.status,{"out_of_scope","scope_uncertain"},result.text)
                self.assertEqual(result.tools_called,())
                self.assertEqual(agent._turns,previous)
            price=agent.run("What is the PIX price for product ID 1?")
            self.assertEqual(price.status,"answered",price.text)
            self.assertIn("90.09",price.text)
            order=agent.run("What is the recorded total for order 1?")
            self.assertEqual(order.status,"answered",order.text)
            self.assertIn("99.00",order.text)

    def test_actual_legitimate_questions_are_in_scope(self):
        provider=self.provider()
        questions=["What is the difference between nylon and steel strings?", "Como conectar um teclado MIDI?",
                   "Compare the two models you listed.","Do you stock a Moog Subsequent 37?",
                   "What are your opening hours?","Quais são as condições de garantia?",
                   "Can you show my authorized order?","What is the recorded total for order 1?"]
        for q in questions:
            with self.subTest(question=q):
                value,_=assess_scope(provider,q,["Please list all available instruments."])
                self.assertEqual(value,"shop")
