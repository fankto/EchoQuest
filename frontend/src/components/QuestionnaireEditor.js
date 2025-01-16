import React, {useState} from 'react';
import {
    Box,
    Button,
    FormControl,
    FormLabel,
    Grid,
    GridItem,
    Heading,
    HStack,
    IconButton,
    Input,
    Textarea,
    useToast,
    VStack,
    Text,
} from '@chakra-ui/react';
import {AddIcon, DeleteIcon} from '@chakra-ui/icons';
import {useNavigate} from 'react-router-dom';

function QuestionnaireEditor() {
    const [title, setTitle] = useState('');
    const [originalContent, setOriginalContent] = useState('');
    const [questions, setQuestions] = useState([]);
    const [file, setFile] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [extractionInProgress, setExtractionInProgress] = useState(false);
    const toast = useToast();
    const navigate = useNavigate();

    const handleFileUpload = async (event) => {
        const selectedFile = event.target.files[0];
        setFile(selectedFile);

        const reader = new FileReader();
        reader.onload = async (e) => {
            const text = e.target.result;
            setOriginalContent(text);
        };
        reader.readAsText(selectedFile);
    };

    const extractQuestions = async () => {
        if (!originalContent) {
            toast({
                title: "Error",
                description: "Please provide content to extract questions from",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            return;
        }

        setExtractionInProgress(true);
        try {
            const formData = new FormData();
            formData.append('title', title || 'Temp Title');
            formData.append('content', originalContent);

            const response = await fetch('/api/questionnaires/', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Failed to extract questions');
            }

            const data = await response.json();
            const extractedQuestions = data.questions?.items || data.questions || [];
            setQuestions(extractedQuestions);

            toast({
                title: "Success",
                description: "Questions extracted successfully",
                status: "success",
                duration: 3000,
                isClosable: true,
            });
        } catch (error) {
            toast({
                title: "Error",
                description: error.message,
                status: "error",
                duration: 3000,
                isClosable: true,
            });
        } finally {
            setExtractionInProgress(false);
        }
    };

    const handleQuestionChange = (index, newValue) => {
        const updatedQuestions = [...questions];
        updatedQuestions[index] = newValue;
        setQuestions(updatedQuestions);
    };

    const addNewQuestion = () => {
        setQuestions([...questions, '']);
    };

    const removeQuestion = (index) => {
        const updatedQuestions = questions.filter((_, i) => i !== index);
        setQuestions(updatedQuestions);
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!title) {
            toast({
                title: "Error",
                description: "Please provide a title",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            return;
        }

        setIsLoading(true);
        try {
            const formData = new FormData();
            formData.append('title', title);
            formData.append('content', originalContent);

            const response = await fetch('/api/questionnaires/', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Failed to save questionnaire');
            }

            toast({
                title: "Success",
                description: "Questionnaire saved successfully",
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

    return (
        <Box p={5} maxW="1200px" mx="auto">
            <form onSubmit={handleSubmit}>
                <VStack spacing={6} align="stretch">
                    <FormControl isRequired>
                        <FormLabel>Questionnaire Title</FormLabel>
                        <Input
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="Enter title"
                        />
                    </FormControl>

                    <Grid templateColumns="repeat(2, 1fr)" gap={6}>
                        <GridItem>
                            <VStack align="stretch" spacing={4}>
                                <FormControl>
                                    <FormLabel>Upload Document (Optional)</FormLabel>
                                    <Input
                                        type="file"
                                        accept=".txt,.doc,.docx,.pdf"
                                        onChange={handleFileUpload}
                                    />
                                </FormControl>

                                <FormControl>
                                    <FormLabel>Document Content</FormLabel>
                                    <Text fontSize="sm" color="gray.600" mb={2}>
                                        Paste your content directly or upload a file above
                                    </Text>
                                    <Textarea
                                        value={originalContent}
                                        onChange={(e) => setOriginalContent(e.target.value)}
                                        placeholder="Enter or paste your document content here"
                                        minHeight="400px"
                                    />
                                </FormControl>

                                {originalContent && (
                                    <FormControl>
                                        <FormLabel>Original Document</FormLabel>
                                        <Textarea
                                            value={originalContent}
                                            onChange={(e) => setOriginalContent(e.target.value)}
                                            minHeight="400px"
                                        />
                                    </FormControl>
                                )}

                                <Button
                                    onClick={extractQuestions}
                                    isLoading={extractionInProgress}
                                    loadingText="Extracting..."
                                    colorScheme="blue"
                                >
                                    Extract Questions
                                </Button>
                            </VStack>
                        </GridItem>

                        <GridItem>
                            <VStack spacing={4} align="stretch">
                                <HStack justify="space-between">
                                    <Heading size="md">Questions</Heading>
                                    <Button
                                        leftIcon={<AddIcon/>}
                                        onClick={addNewQuestion}
                                        colorScheme="blue"
                                        size="sm"
                                    >
                                        Add Question
                                    </Button>
                                </HStack>

                                <VStack spacing={2} align="stretch" maxH="500px" overflowY="auto">
                                    {questions.map((question, index) => (
                                        <HStack key={index} spacing={2}>
                                            <Input
                                                value={question}
                                                onChange={(e) => handleQuestionChange(index, e.target.value)}
                                                placeholder="Enter question"
                                            />
                                            <IconButton
                                                icon={<DeleteIcon/>}
                                                onClick={() => removeQuestion(index)}
                                                colorScheme="red"
                                                aria-label="Remove question"
                                            />
                                        </HStack>
                                    ))}
                                </VStack>
                            </VStack>
                        </GridItem>
                    </Grid>

                    <Button
                        type="submit"
                        colorScheme="green"
                        size="lg"
                        isLoading={isLoading}
                        loadingText="Saving..."
                        mt={4}
                    >
                        Save Questionnaire
                    </Button>
                </VStack>
            </form>
        </Box>
    );
}

export default QuestionnaireEditor;