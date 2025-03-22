extraction_messages = [
    {
        "role": "system",
        "content": "You are tasked with extracting relevant parts from interview questionnaires and similar texts. Extract ONLY questions, prompts, or instructions that are explicitly structured to elicit answers. Each extracted item should be returned verbatim as it appears in the source text. The output should be a JSON object with an 'extracted_items' array containing objects with 'item' and 'exact_match' properties."
    },
    {
        "role": "user",
        "content": "Extract all relevant questions, prompts, and instructions from the following content, maintaining exact wording: \"{content}\"\n\nReturn ONLY the JSON object with the extracted items."
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