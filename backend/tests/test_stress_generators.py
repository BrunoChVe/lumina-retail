import unittest
import asyncio
from datetime import datetime
from scripts.stress_kafka import generate_synthetic_event, run_stage
from scripts.stress_http_api import run_http_stage


class TestStressGenerators(unittest.TestCase):
    def test_synthetic_event_schema(self):
        test_run_id = "test-uuid-1234"
        event = generate_synthetic_event(test_run_id, 1)

        self.assertIn("test_run_id", event)
        self.assertEqual(event["test_run_id"], test_run_id)
        self.assertEqual(event["event_type"], "SYNTHETIC_CYBERDAY_STRESS")
        self.assertEqual(event["region"], "CYBER_TEST")
        self.assertTrue(event["product_id"].startswith("CYBER_PROD_"))
        self.assertGreater(event["stock"], 0)

        # Validar fecha ISO 8601
        dt = datetime.fromisoformat(event["timestamp"])
        self.assertIsNotNone(dt)

    def test_kafka_stage_dry_run(self):
        # Ejecutar 1 segundo a 10 msgs/s en dry run (sin conectar a Kafka)
        success, sent, errs, latencies = run_stage(
            producer=None,
            topic="test-topic",
            rate=10,
            duration_sec=1,
            test_run_id="dry-run-id",
            dry_run=True
        )
        self.assertTrue(success)
        self.assertGreaterEqual(sent, 8)
        self.assertEqual(errs, 0)
        self.assertEqual(len(latencies), sent)

    def test_http_stage_dry_run(self):
        # Ejecutar etapa HTTP en modo dry run
        success, reqs, errs, rps, latencies = asyncio.run(
            run_http_stage(
                base_url="http://mock-service",
                endpoint="/api/health",
                concurrency=2,
                duration_sec=1,
                dry_run=True
            )
        )
        self.assertTrue(success)
        self.assertEqual(reqs, 50)
        self.assertEqual(errs, 0)


if __name__ == "__main__":
    unittest.main()
