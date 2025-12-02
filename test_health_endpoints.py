"""Test health endpoints by making HTTP requests."""

import requests
import time
import subprocess
import signal
import os
from threading import Thread

def test_health_endpoints():
    """Test that health monitoring endpoints work."""
    # Start the Flask app in background
    app_process = subprocess.Popen(
        ['python', 'app.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )
    
    try:
        # Wait for app to start
        time.sleep(3)
        
        base_url = "http://127.0.0.1:8080"
        
        # Test basic health endpoint (backward compatibility)
        try:
            response = requests.get(f"{base_url}/api/health", timeout=5)
            print(f"Basic health endpoint status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Basic health response: {data}")
            else:
                print(f"Basic health error: {response.text}")
        except Exception as e:
            print(f"Basic health endpoint error: {e}")
        
        # Test liveness probe
        try:
            response = requests.get(f"{base_url}/api/health/live", timeout=5)
            print(f"Liveness probe status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Liveness response: {data}")
        except Exception as e:
            print(f"Liveness probe error: {e}")
        
        # Test readiness probe
        try:
            response = requests.get(f"{base_url}/api/health/ready", timeout=5)
            print(f"Readiness probe status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Readiness response: {data}")
        except Exception as e:
            print(f"Readiness probe error: {e}")
        
        # Test deep health check
        try:
            response = requests.get(f"{base_url}/api/health/deep", timeout=10)
            print(f"Deep health check status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Deep health response keys: {list(data.keys())}")
                if 'checks' in data:
                    print(f"Health checks performed: {list(data['checks'].keys())}")
        except Exception as e:
            print(f"Deep health check error: {e}")
        
        # Test metrics endpoint
        try:
            response = requests.get(f"{base_url}/api/health/metrics", timeout=5)
            print(f"Metrics endpoint status: {response.status_code}")
            if response.status_code == 200:
                print("Metrics response (first few lines):")
                lines = response.text.split('\n')[:10]
                for line in lines:
                    if line.strip():
                        print(f"  {line}")
        except Exception as e:
            print(f"Metrics endpoint error: {e}")
            
    finally:
        # Terminate the app process
        os.killpg(os.getpgid(app_process.pid), signal.SIGTERM)
        app_process.wait()

if __name__ == '__main__':
    test_health_endpoints()