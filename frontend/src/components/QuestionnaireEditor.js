import React, { useState, useEffect } from 'react';
import { Box, VStack, Heading, Input, Textarea, Button, useToast, FormControl, FormLabel, Switch } from '@chakra-ui/react';
import { useParams, useNavigate } from 'react-router-dom';

function QuestionnaireEditor() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [title, setTitle] = useState('');
    const [content, setContent] = useState('');
    const [file, setFile] = useState(null);
    const [isManualInput, setIsManualInput] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const toast = useToast();

    useEffect(() => {
        if (id) {
            fetchQuestionnaire();
        }
    }, [id]);

    const fetchQuestionnaire = async () => {
        try {
            const response = await fetch(`/api/questionnaires/${id}`);
            if (response.ok) {
                const data = await response.json();
                setTitle(data.title);
                setContent(data.content);
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
    };

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

        const method = id ? 'PUT' : 'POST';
        const url = id ? `/api/questionnaires/${id}` : '/api/questionnaires/';

        setIsLoading(true);

        try {
            const response = await fetch(url, {
                method: method,
                body: formData,
            });
            if (response.ok) {
                toast({
                    title: "Success",
                    description: `Questionnaire ${id ? 'updated' : 'created'} successfully`,
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                navigate('/');
            } else {
                throw new Error(`Failed to ${id ? 'update' : 'create'} questionnaire`);
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
        finally {
            setIsLoading(false);
        }
    };

    const handleFileChange = (event) => {
        setFile(event.target.files[0]);
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
                    <Button
                        type="submit"
                        colorScheme="blue"
                        isLoading={isLoading}
                        loadingText={id ? 'Updating...' : 'Creating...'}
                        width="200px"
                    >
                        {id ? 'Update Questionnaire' : 'Create Questionnaire'}
                    </Button>
                </VStack>
            </form>
        </Box>
    );
}

export default QuestionnaireEditor;