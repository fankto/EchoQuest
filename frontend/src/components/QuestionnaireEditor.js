// frontend/src/components/QuestionnaireEditor.js
import React, { useCallback, useEffect, useState } from 'react';
import {
    Box,
    Button,
    FormControl,
    FormLabel,
    Heading,
    Input,
    Switch,
    Textarea,
    useToast,
    VStack,
} from '@chakra-ui/react';
import { useNavigate, useParams } from 'react-router-dom';
import EditableQuestions from './EditableQuestions';

function QuestionnaireEditor() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [title, setTitle] = useState('');
    const [content, setContent] = useState('');
    const [extractedQuestions, setExtractedQuestions] = useState([]);
    const [file, setFile] = useState(null);
    const [isManualInput, setIsManualInput] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const toast = useToast();

    const fetchQuestionnaire = useCallback(async () => {
        if (!id) return;

        try {
            const response = await fetch(`/api/questionnaires/${id}`);
            if (response.ok) {
                const data = await response.json();
                setTitle(data.title);
                setContent(data.content);
                setExtractedQuestions(data.questions || []);
            } else {
                throw new Error('Failed to fetch questionnaire');
            }
        } catch (error) {
            toast({
                title: "Error",
                description: error.message,
                status: "error",
                duration: 3000,
                isClosable: true,
            });
        }
    }, [id, toast]);

    useEffect(() => {
        fetchQuestionnaire();
    }, [fetchQuestionnaire]);

    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!title || (!content && !file && !isManualInput)) {
            toast({
                title: "Error",
                description: "Please fill all required fields.",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            return;
        }

        const formData = new FormData();
        formData.append('title', title);
        if (isManualInput) {
            formData.append('content', content);
        } else if (file) {
            formData.append('file', file);
        }
        formData.append('questions', JSON.stringify(extractedQuestions));

        setIsLoading(true);
        try {
            const method = id ? 'PUT' : 'POST';
            const url = id ? `/api/questionnaires/${id}` : '/api/questionnaires/';

            const response = await fetch(url, {
                method: method,
                body: formData,
            });

            if (!response.ok) {
                throw new Error(`Failed to ${id ? 'update' : 'create'} questionnaire`);
            }

            toast({
                title: "Success",
                description: `Questionnaire ${id ? 'updated' : 'created'} successfully`,
                status: "success",
                duration: 3000,
                isClosable: true,
            });
            navigate('/');
        } catch (error) {
            toast({
                title: "Error",
                description: error.message,
                status: "error",
                duration: 3000,
                isClosable: true,
            });
        } finally {
            setIsLoading(false);
        }
    };

    const handleFileChange = async (event) => {
        const selectedFile = event.target.files[0];
        setFile(selectedFile);

        if (selectedFile) {
            const reader = new FileReader();
            reader.onload = async (e) => {
                const text = e.target.result;
                setContent(text);

                // Extract questions from the file content
                try {
                    const formData = new FormData();
                    formData.append('content', text);

                    const response = await fetch('/api/questionnaires/', {
                        method: 'POST',
                        body: formData,
                    });

                    if (response.ok) {
                        const data = await response.json();
                        setExtractedQuestions(data.questions || []);
                    }
                } catch (error) {
                    toast({
                        title: "Error",
                        description: "Failed to extract questions from file",
                        status: "error",
                        duration: 3000,
                        isClosable: true,
                    });
                }
            };
            reader.readAsText(selectedFile);
        }
    };

    const handleQuestionsChange = (newQuestions) => {
        setExtractedQuestions(newQuestions);
    };

    return (
        <Box p={5}>
            <Heading mb={5}>{id ? 'Edit Questionnaire' : 'Create New Questionnaire'}</Heading>
            <form onSubmit={handleSubmit}>
                <VStack spacing={4} align="stretch">
                    <Input
                        placeholder="Questionnaire Title"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                    />

                    <FormControl display="flex" alignItems="center">
                        <FormLabel htmlFor="manual-input" mb="0">
                            Manual Input
                        </FormLabel>
                        <Switch
                            id="manual-input"
                            isChecked={isManualInput}
                            onChange={(e) => setIsManualInput(e.target.checked)}
                        />
                    </FormControl>

                    {isManualInput ? (
                        <Textarea
                            placeholder="Questionnaire Content"
                            value={content}
                            onChange={(e) => setContent(e.target.value)}
                            minHeight="200px"
                        />
                    ) : (
                        <Input
                            type="file"
                            accept=".docx,.pdf,.txt"
                            onChange={handleFileChange}
                        />
                    )}

                    <Box mt={4}>
                        <Heading size="md" mb={4}>Questions</Heading>
                        <EditableQuestions
                            questions={extractedQuestions}
                            onChange={handleQuestionsChange}
                        />
                    </Box>

                    <Button
                        type="submit"
                        colorScheme="blue"
                        isLoading={isLoading}
                        loadingText={id ? 'Updating...' : 'Creating...'}
                        width="200px"
                        mt={4}
                    >
                        {id ? 'Update Questionnaire' : 'Create Questionnaire'}
                    </Button>
                </VStack>
            </form>
        </Box>
    );
}

export default QuestionnaireEditor;