"""
Quick API test script.

Run this after starting the FastAPI server to verify endpoints work.
"""

import requests
import time

API_URL = "http://localhost:5001"


def test_health():
    """Test health endpoint."""
    print("\n1. Testing health endpoint...")
    response = requests.get(f"{API_URL}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200


def test_create_session():
    """Test creating an analysis session."""
    print("\n2. Creating analysis session...")
    response = requests.post(
        f"{API_URL}/api/analysis/start",
        json={"ticker": "AAPL"}
    )
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Session ID: {data['session_id']}")
    print(f"   Ticker: {data['ticker']}")
    assert response.status_code == 201
    return data['session_id']


def test_session_status(session_id):
    """Test getting session status."""
    print("\n3. Getting session status...")
    response = requests.get(f"{API_URL}/api/analysis/{session_id}/status")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Message count: {data['message_count']}")
    print(f"   Beliefs: {data['beliefs_count']}")
    assert response.status_code == 200


def test_run_analysis(session_id):
    """Test running analysis (SSE stream)."""
    print("\n4. Running analysis (SSE stream)...")
    print("   Streaming progress:")

    response = requests.post(
        f"{API_URL}/api/analysis/{session_id}/run",
        stream=True
    )

    for line in response.iter_lines():
        if line:
            decoded = line.decode('utf-8')
            if decoded.startswith('data:'):
                print(f"   {decoded}")

    print("   Analysis complete!")


def test_get_sections(session_id):
    """Test getting report sections."""
    print("\n5. Getting report sections...")
    response = requests.get(f"{API_URL}/api/reports/{session_id}/sections")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Sections: {list(data['sections'].keys())}")
    assert response.status_code == 200


def test_chat_stream(session_id):
    """Test chat streaming."""
    print("\n6. Testing chat stream...")
    print("   Sending: 'What is the P/E ratio?'")

    url = f"{API_URL}/api/chat/stream"
    params = {
        'session_id': session_id,
        'message': 'What is the P/E ratio?'
    }

    response = requests.get(url, params=params, stream=True)
    full_response = ""

    for line in response.iter_lines():
        if line:
            decoded = line.decode('utf-8')
            if decoded.startswith('data:'):
                chunk = decoded[6:]  # Remove 'data: '
                if chunk == '[DONE]':
                    break
                full_response += chunk

    print(f"   Response: {full_response[:100]}...")


def test_get_history(session_id):
    """Test getting conversation history."""
    print("\n7. Getting conversation history...")
    response = requests.get(f"{API_URL}/api/chat/{session_id}/history")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Messages: {len(data['messages'])}")
    if data['messages']:
        print(f"   Last message: {data['messages'][-1]['content'][:50]}...")


def test_get_beliefs(session_id):
    """Test getting beliefs."""
    print("\n8. Getting beliefs...")
    response = requests.get(f"{API_URL}/api/chat/{session_id}/beliefs")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Belief count: {len(data['beliefs'])}")
    print(f"   Stats: {data['stats']}")


def test_list_sessions():
    """Test listing all sessions."""
    print("\n9. Listing all sessions...")
    response = requests.get(f"{API_URL}/api/analysis/sessions")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Total sessions: {data['count']}")


def run_all_tests():
    """Run all API tests."""
    print("=" * 60)
    print("George Research - API Test Suite")
    print("=" * 60)

    try:
        # Health check
        test_health()

        # Create session and run analysis
        session_id = test_create_session()
        test_session_status(session_id)
        test_run_analysis(session_id)

        # Wait for analysis to complete
        time.sleep(1)

        # Test reports
        test_get_sections(session_id)

        # Test chat
        test_chat_stream(session_id)
        time.sleep(0.5)
        test_get_history(session_id)
        test_get_beliefs(session_id)

        # List sessions
        test_list_sessions()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
    except requests.exceptions.ConnectionError:
        print("\nERROR: Could not connect to API.")
        print("Make sure the FastAPI server is running:")
        print("  ./start.sh  # or: uv run uvicorn backend.main:app --port 5001")
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
