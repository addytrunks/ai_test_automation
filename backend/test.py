import litellm

from app.config import Settings

settings = Settings()
litellm.api_key = settings.gemini_api_key

response = litellm.completion(
    model=settings.llm_model,
    messages=[{"role": "user", "content": "Hi there! How is it going? What's 5+2?"}],
)

print(response.choices[0].message.content)
print("Prompt Usage: ", response.usage.prompt_tokens)
print("Completion Usage: ", response.usage.completion_tokens)
print("Total Usage: ", response.usage.total_tokens)