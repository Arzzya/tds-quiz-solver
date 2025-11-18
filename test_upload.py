import requests
import json

def test_upload():
    url = "http://127.0.0.1:8001/upload"
    
    # Prepare form data
    data = {
        "email": "you@example.com",
        "secret": "my-super-secret"
    }
    
    with open('test_value.csv', 'rb') as f:
        files = {'file': ('test_value.csv', f, 'text/csv')}
        response = requests.post(url, data=data, files=files)
    
    print("Status Code:", response.status_code)
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    
    # Check if it calculated the correct sum (10 + 20.5 + 3 = 33.5)
    if response.status_code == 200:
        result = response.json()
        if result.get('answer') == 33.5:
            print("✅ SUCCESS: Correctly calculated sum 33.5!")
        else:
            print(f"❌ Expected 33.5, got {result.get('answer')}")

if __name__ == "__main__":
    test_upload()