import time
import threading
import requests
import json

class TokenBucket:
    """Simple Token Bucket for Rate Limiting"""
    def __init__(self, capacity, refill_rate):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens_needed):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            
            # Refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            
            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                return True
            return False

# 6000 TPM limit (using half of 12k to be safe) => 100 tokens per sec
groq_rate_limiter = TokenBucket(capacity=4000, refill_rate=50) 

def call_groq_api(messages, temperature=0.7, max_tokens=1500, retries=3):
    """Appel à l'API Groq avec retry exponentiel et Token Bucket"""
    
    # Estimate tokens (approximation: 1 word = 1.3 tokens)
    input_text = json.dumps(messages)
    estimated_tokens = len(input_text) // 3 
    
    # Wait for capacity
    wait_attempts = 0
    while not groq_rate_limiter.consume(estimated_tokens):
        wait_attempts += 1
        # Stop waiting after 2 seconds to fail fast for UI responsiveness
        if wait_attempts > 20: 
             # Silently fail to keep console clean, caller handles it.
             return "Erreur API: Rate Limit Internal - Skipped"
        time.sleep(0.1)
    
    backoff = 2  # Reduced to 2s for faster UI feedback

    for attempt in range(retries):
        try:
            response = requests.post(
                GROQ_API_URL,
                headers={
                    'Authorization': f'Bearer {GROQ_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': GROQ_MODEL,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                },
                timeout=15 # Reduced timeout further
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content']
                else:
                    return f"Erreur API: Réponse vide"
            elif response.status_code == 429:
                if attempt == retries - 1:
                    return "Erreur API (429): Rate Limit Exceeded"
                
                # print(f"[WARN] Groq Rate Limit (429)...") # Silenced
                time.sleep(backoff)
                backoff *= 1.5
            else:
                return f"Erreur API: {response.status_code}"
        except Exception as e:
            # print(f"Erreur tentative {attempt+1}: {e}") # Silenced
            if attempt == retries - 1:
                return f"Erreur: {str(e)}"
            time.sleep(2)
            
    return "Erreur API: Max retries exceeded"
