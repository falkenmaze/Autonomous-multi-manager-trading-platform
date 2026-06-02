import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from remote_controller import app

def test_index():
    print("🧪 Testing '/' route...")
    try:
        with app.test_client() as client:
            response = client.get('/')
            print(f"Status Code: {response.status_code}")
            print(f"Response Data (first 100 chars): {response.data[:100]}")
            
            if response.status_code == 200:
                print("✅ Test Passed!")
            else:
                print("❌ Test Failed!")
    except Exception as e:
        print(f"❌ Exception during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_index()
