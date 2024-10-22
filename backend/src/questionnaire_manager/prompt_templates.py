extraction_messages = [
    {
        "role": "system",
        "content": "You are tasked with extracting relevant parts from interview questionnaires and similar texts. Extract ONLY questions, prompts, or instructions (e.g., 'Who is speaking?', 'What are the key takeaways?', 'List the key recommendations') that are **explicitly structured to elicit answers**. Do NOT include any meta-information, explanations, or any other statements (e.g., 'these are questions that...') that are not actual questions, prompts, or instructions. The extracted items will later be used to generate answers based on an interview transcript. The output should be a JSON object with an 'items' key containing an array of the extracted relevant questions, prompts, and instructions. Example output: {\"items\": [\"Who is speaking?\", \"What are the key takeaways?\", \"List the key recommendations.\"]}"
    },
    {
        "role": "user",
        "content": "Extract all relevant questions, prompts, and instructions **explicitly structured to elicit answers** from the following content, considering their use in generating answers from an interview transcript. Do NOT extract any explanatory statements or comments: \"{content}\"\n\nReturn ONLY the JSON object with the extracted relevant items."
    }
]

verification_messages = [
    {
        "role": "system",
        "content": "Your task is to verify the accuracy of the extraction. Check if all relevant questions, prompts, or instructions (e.g., 'Who is speaking?', 'What are the key takeaways?', 'List the key recommendations') that are **explicitly structured to elicit answers** have been correctly extracted. Do NOT include any meta-information, explanations, or any other statements that are not actual questions, prompts, or instructions. If any irrelevant or incorrect items were extracted, or if relevant items were missed, provide a complete corrected JSON object. If everything is correct, respond with only the word 'yes'. Example of a corrected JSON (only if needed): {\"items\": [\"Who is speaking?\", \"What are the key takeaways?\", \"List the key recommendations.\"]}"
    },
    {
        "role": "user",
        "content": "Original content: \"{content}\"\n\nExtracted items: \"{extracted_items}\"\n\nVerify if all relevant questions, prompts, and instructions **explicitly structured to elicit answers** from the provided content have been correctly extracted. Do NOT include any explanatory statements or meta-information. If yes, respond with only 'yes'. If no, provide a complete JSON object with all correct relevant items."
    }
]
