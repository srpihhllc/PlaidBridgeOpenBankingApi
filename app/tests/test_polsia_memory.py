
import json

from unittest.mock import MagicMock, patch



from app.services.polsia_memory import PolsiaMemoryStore





def test_polsia_memory_roundtrip_and_prompt_formatting():

    fake_redis = MagicMock()

    stored = []



    def _lpush(key, val):

        stored.insert(0, val)



    def _lrange(key, start, end):

        return stored[start : end + 1]



    fake_redis.lpush.side_effect = _lpush

    fake_redis.lrange.side_effect = _lrange



    with patch("app.services.polsia_memory.get_redis_client", return_value=fake_redis):

        store = PolsiaMemoryStore()

        store.record_outcome(

            {

                "task_id": "task_901",

                "company_id": "comp_plaidbridge_01",

                "event": "task.completed",

                "agent_id": "finbrain-risk-analyzer",

                "result": {

                    "summary": "Detected predatory APR escalation on lender_42",

                    "anomalies": ["apr_spike"],

                },

            }

        )



        insights = store.get_recent_insights(company_id="comp_plaidbridge_01", limit=5)

        assert len(insights) == 1

        assert insights[0]["task_id"] == "task_901"



        prompt_ctx = store.format_prompt_context(company_id="comp_plaidbridge_01")

        assert "LEARNED_CORTEX_MEMORY" in prompt_ctx

        assert "predatory APR escalation" in prompt_ctx

