extraction_messages = [
    {
        "role": "system",
        "content": "Your task is to identify and extract VERBATIM questions, prompts, or instructions from the provided text. Do not modify, rephrase, or create new questions. Only extract items that are explicitly written as questions or direct instructions in the source text (e.g. 'What is your name?', 'Describe your role.'). Include only complete, unmodified questions/prompts exactly as they appear in the text. Exclude any surrounding text, explanations, or context. Output format: {\"items\": [\"<exact question 1>\", \"<exact question 2>\"]}. Each extracted item must be a word-for-word match from the source text."
    },
    {
        "role": "user",
        "content": "Extract ONLY the exact, word-for-word questions, prompts, and instructions from the following text. Do not modify or create new questions. Extract only complete questions/prompts that appear explicitly in the text: \"{content}\"\n\nReturn ONLY the JSON object with the verbatim extracted items."
    }
]

verification_messages = [
    {
        "role": "system",
        "content": "Verify that each extracted item appears word-for-word in the original text. Check that: 1) Every extracted item exists verbatim in the source text, 2) No modifications were made to any extracted items, 3) No questions were created or combined, 4) Only explicit questions/prompts were extracted. If any item fails these criteria or if relevant items were missed, provide a corrected JSON with exact matches from the text. If all items are verbatim matches, respond with only 'yes'."
    },
    {
        "role": "user",
        "content": "Original text: \"{content}\"\n\nExtracted items: \"{extracted_items}\"\n\nVerify that each extracted item appears exactly, word-for-word in the original text. Check for any modifications or missed items. If all items are exact matches, respond with only 'yes'. If any discrepancies exist, provide a JSON object with the correct verbatim extractions."
    }
]