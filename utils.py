import requests

def load_model(model_name="llama2.11b.fimbulvetr-v2.gguf_v2.q4_k_m.gguf"):
    load_response = requests.post(
        'http://127.0.0.1:5000/v1/internal/model/load',
        json={"model_name": model_name}
    )
    if load_response.status_code != 200:
        raise Exception(f"Failed to load the model: {model_name}")
    print(f"Model {model_name} loaded successfully.")

def unload_model():
    unload_response = requests.post('http://127.0.0.1:5000/v1/internal/model/unload')
    if unload_response.status_code != 200:
        raise Exception("Failed to unload the model.")
    print("Model unloaded successfully.")

