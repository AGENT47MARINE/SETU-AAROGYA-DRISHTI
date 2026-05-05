import json
import random
import time
from datetime import datetime
from kafka import KafkaProducer

def generate_stress_data(num_posts=50):
    platforms = ["X", "Sharechat", "Facebook"]
    # Varied health signals (Hindi, English, Mixed)
    texts = [
        "Mere ghar mein sabko fever hai. Bohot tension ho rahi hai.",
        "Sudden surge in cough and cold cases in Arera Colony, Bhopal.",
        "My child has high fever since morning. Paracetamol not working.",
        "Bhopal ke is area mein bohot log bimar pad rahe hain. Vomiting and nausea symptoms.",
        "Hospital is crowded today. Many people with breathing issues.",
        "Getting dizzy after taking my routine medicine.",
        "I feel very weak and have body aches.",
        "Medical shops are running out of common antibiotics here.",
        "Feeling better after rest, but my neighbor also has similar fever.",
        "Is there a virus going around? Everyone in my office is coughing."
    ]
    
    producer = KafkaProducer(
        bootstrap_servers="localhost:29092",
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    print(f"🚀 Starting Stress Test: Sending {num_posts} signals...")
    
    for i in range(num_posts):
        post = {
            "id": f"stress_{i}_{int(time.time())}",
            "platform": random.choice(platforms),
            "text": random.choice(texts),
            "posted_at": datetime.utcnow().isoformat(),
            "location": {
                "lat": 23.25 + (random.random() * 0.05), # Randomized around Bhopal
                "lng": 77.41 + (random.random() * 0.05)
            }
        }
        producer.send("raw_posts", post)
        if i % 10 == 0:
            print(f"Sent {i} posts...")
        time.sleep(0.5) # Simulate burst traffic
        
    producer.flush()
    print("✅ Stress Test signals sent.")

if __name__ == "__main__":
    generate_stress_data(50)
