curl -X POST "http://localhost:8111/experiments/run" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_path":"dataset.jsonl",
    "techniques":["zero_shot","few_shot","chain_of_thought","role_prompting"],
    "runs_per_technique":3,
    "model_name":"gemma4:e2b-CC",
    "params":{"temperature":0.2,"max_tokens":120}
  }'
