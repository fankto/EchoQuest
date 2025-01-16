// frontend/src/components/EditableQuestions.js
import React, { useState } from 'react';
import { VStack, HStack, Input, IconButton, Button } from '@chakra-ui/react';
import { AddIcon, DeleteIcon } from '@chakra-ui/icons';

const EditableQuestions = ({ questions: initialQuestions = [], onChange }) => {
    const [questions, setQuestions] = useState(initialQuestions);

    const handleQuestionChange = (index, value) => {
        const newQuestions = [...questions];
        newQuestions[index] = value;
        setQuestions(newQuestions);
        onChange(newQuestions);
    };

    const addQuestion = () => {
        const newQuestions = [...questions, ''];
        setQuestions(newQuestions);
        onChange(newQuestions);
    };

    const removeQuestion = (index) => {
        const newQuestions = questions.filter((_, i) => i !== index);
        setQuestions(newQuestions);
        onChange(newQuestions);
    };

    return (
        <VStack spacing={3} align="stretch">
            {questions.map((question, index) => (
                <HStack key={index}>
                    <Input
                        value={question}
                        onChange={(e) => handleQuestionChange(index, e.target.value)}
                        placeholder="Enter question"
                    />
                    <IconButton
                        icon={<DeleteIcon />}
                        onClick={() => removeQuestion(index)}
                        aria-label="Remove question"
                        colorScheme="red"
                    />
                </HStack>
            ))}
            <Button
                leftIcon={<AddIcon />}
                onClick={addQuestion}
                size="sm"
                width="fit-content"
            >
                Add Question
            </Button>
        </VStack>
    );
};

export default EditableQuestions;