# src/question_answerer/prompt_templates.py

question_answering_messages = [
    {
        "role": "system",
        "content": """You are a helpful AI assistant. Your task is to answer the given question based solely on the provided context. If the question cannot be answered using the given context, explain why and describe any relevant information you can extract from the context, such as the speaker's tone, attitude, or general implications. Always strive to provide the most accurate and relevant answer possible."""
    },
    {
        "role": "user",
        "content": """Context: {context}

Question: {question}

Please answer the question based only on the information provided in the context. If you cannot answer directly, explain why and describe any relevant insights from the context."""
    }
]