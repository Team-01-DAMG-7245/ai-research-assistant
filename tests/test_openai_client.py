"""
Tests for OpenAI Client Utility
Tests for OpenAI client with retry logic, error handling, and cost tracking
"""

import pytest
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

from src.utils.openai_client import OpenAIClient, UsageStats, PRICING


class TestOpenAIClientImport:
    """Test that module imports correctly"""

    def test_module_import(self):
        """Test that module imports successfully"""
        print("\n🧪 Testing module import...")
        from src.utils.openai_client import OpenAIClient, UsageStats, PRICING

        print("   ✅ Module imported successfully")
        assert True


class TestOpenAIClientInitialization:
    """Test client initialization"""

    def test_missing_api_key(self):
        """Test error handling when API key is missing"""
        print("\n🧪 Testing missing API key error handling...")

        # Temporarily remove API key from environment
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="OpenAI API key not found"):
                client = OpenAIClient()
            print("   ✅ Correctly raised ValueError for missing API key")
        finally:
            # Restore API key if it existed
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key

    def test_client_initialization_with_key(self):
        """Test client initialization with API key"""
        print("\n🧪 Testing client initialization...")
        client = OpenAIClient(api_key="test-key-12345")
        assert client is not None
        assert client.api_key == "test-key-12345"
        print("   ✅ Client initialized successfully")


class TestTokenCounting:
    """Test token counting functionality"""

    @pytest.fixture
    def client(self):
        """Create a test client instance"""
        return OpenAIClient(api_key="test-key-12345")

    def test_simple_text_token_counting(self, client):
        """Test token counting for simple text"""
        print("\n🧪 Testing simple text token counting...")
        text = "Hello world, this is a test sentence."
        tokens = client.count_tokens(text, "gpt-3.5-turbo")
        assert tokens > 0
        print(f"   ✅ Simple text: '{text}' = {tokens} tokens")

    def test_longer_text_token_counting(self, client):
        """Test token counting for longer text"""
        print("\n🧪 Testing longer text token counting...")
        long_text = "This is a longer text that should have more tokens. " * 10
        tokens = client.count_tokens(long_text, "gpt-3.5-turbo")
        assert tokens > 0
        print(f"   ✅ Longer text: {len(long_text)} chars = {tokens} tokens")

    def test_chat_messages_token_counting(self, client):
        """Test token counting for chat messages"""
        print("\n🧪 Testing chat messages token counting...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is machine learning?"},
        ]
        tokens = client.count_tokens(messages, "gpt-3.5-turbo")
        assert tokens > 0
        print(f"   ✅ Chat messages: {tokens} tokens")


class TestCostCalculation:
    """Test cost calculation"""

    @pytest.fixture
    def client(self):
        """Create a test client instance"""
        return OpenAIClient(api_key="test-key-12345")

    def test_gpt35_turbo_cost_calculation(self, client):
        """Test cost calculation for GPT-3.5-turbo"""
        print("\n🧪 Testing GPT-3.5-turbo cost calculation...")
        cost = client._calculate_cost("gpt-3.5-turbo", 1000, 500)
        expected = (1000 / 1000) * 0.0015 + (500 / 1000) * 0.002
        assert abs(cost - expected) < 0.000001, "Cost calculation mismatch"
        print(f"   ✅ GPT-3.5-turbo: 1000 prompt + 500 completion tokens = ${cost:.6f}")

    def test_embedding_cost_calculation(self, client):
        """Test cost calculation for embedding model"""
        print("\n🧪 Testing embedding model cost calculation...")
        cost = client._calculate_cost("text-embedding-3-small", 1000, 0)
        expected = (1000 / 1000) * 0.00002
        assert abs(cost - expected) < 0.000001, "Embedding cost calculation mismatch"
        print(f"   ✅ text-embedding-3-small: 1000 tokens = ${cost:.6f}")


class TestUsageStatistics:
    """Test usage statistics tracking"""

    @pytest.fixture
    def client(self):
        """Create a test client instance"""
        return OpenAIClient(api_key="test-key-12345")

    def test_stats_tracking(self, client):
        """Test that usage statistics are tracked correctly"""
        print("\n🧪 Testing usage statistics tracking...")

        # Manually update stats (simulating API calls)
        client._update_stats("gpt-3.5-turbo", 100, 50, 0.001)
        client._update_stats("text-embedding-3-small", 1000, 0, 0.00002)

        stats = client.get_usage_stats()

        assert stats["total_requests"] == 2
        assert stats["total_tokens"] == 1150
        assert stats["total_cost"] == 0.00102

        print(f"   ✅ Total requests: {stats['total_requests']}")
        print(f"   ✅ Total tokens: {stats['total_tokens']}")
        print(f"   ✅ Total cost: ${stats['total_cost']:.6f}")
        print(f"   ✅ Requests by model: {stats['requests_by_model']}")

    def test_stats_reset(self, client):
        """Test that stats can be reset"""
        print("\n🧪 Testing stats reset...")

        # Update stats first
        client._update_stats("gpt-3.5-turbo", 100, 50, 0.001)

        # Reset stats
        client.reset_stats()
        stats_after = client.get_usage_stats()

        assert stats_after["total_requests"] == 0
        assert stats_after["total_tokens"] == 0
        assert stats_after["total_cost"] == 0.0

        print("   ✅ Stats reset works correctly")


class TestPricingTable:
    """Test pricing table completeness"""

    def test_required_models_have_pricing(self):
        """Test that all required models have pricing"""
        print("\n🧪 Testing pricing table completeness...")

        required_models = [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "text-embedding-ada-002",
            "text-embedding-3-small",
            "text-embedding-3-large",
        ]

        missing = [model for model in required_models if model not in PRICING]

        assert len(missing) == 0, f"Missing pricing for: {missing}"
        print("   ✅ All required models have pricing")
        print(f"      Available models: {list(PRICING.keys())}")

    def test_pricing_structure_valid(self):
        """Test that all pricing structures are valid"""
        print("\n🧪 Testing pricing structure validity...")

        for model, prices in PRICING.items():
            assert "input" in prices, f"Missing 'input' pricing for {model}"
            assert "output" in prices, f"Missing 'output' pricing for {model}"

        print("   ✅ All pricing structures are valid")


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
