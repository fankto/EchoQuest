import React, {useCallback, useEffect, useState} from 'react';
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
    Text,
    Textarea,
    useToast,
    VStack,
} from '@chakra-ui/react';
import {AddIcon, DeleteIcon} from '@chakra-ui/icons';
import {Link, useNavigate, useParams} from 'react-router-dom';

function ViewQuestionnaire() {
    const {id} = useParams();
    const [questionnaire, setQuestionnaire] = useState(null);
    const [editedTitle, setEditedTitle] = useState('');
    const [editedContent, setEditedContent] = useState('');
    const [questions, setQuestions] = useState([]);
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [isExtracting, setIsExtracting] = useState(false);
    const toast = useToast();
    const navigate = useNavigate();

    const fetchQuestionnaire = useCallback(async () => {
        try {
            const response = await fetch(`/api/questionnaires/${id}`);
            if (response.ok) {
                const data = await response.json();
                setQuestionnaire(data);
                setEditedTitle(data.title);
                setEditedContent(data.content);
                setQuestions(data.questions || []);
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

    const extractQuestions = async () => {
        if (!editedContent) {
            toast({
                title: "Error",
                description: "Please provide content to extract questions from",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            return;
        }

        setIsExtracting(true);
        try {
            const formData = new FormData();
            formData.append('title', editedTitle);
            formData.append('content', editedContent);

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
            setIsExtracting(false);
        }
    };

    const handleSave = async () => {
        if (!editedTitle) {
            toast({
                title: "Error",
                description: "Please provide a title",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            return;
        }

        setIsSaving(true);
        try {
            const formData = new FormData();
            formData.append('title', editedTitle);
            formData.append('content', editedContent);

            const response = await fetch(`/api/questionnaires/${id}`, {
                method: 'PUT',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Failed to update questionnaire');
            }

            setIsEditing(false);
            fetchQuestionnaire();

            toast({
                title: "Success",
                description: "Questionnaire updated successfully",
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
            setIsSaving(false);
        }
    };

    const handleDelete = async () => {
        if (window.confirm("Are you sure you want to delete this questionnaire?")) {
            try {
                const response = await fetch(`/api/questionnaires/${id}`, {
                    method: 'DELETE',
                });
                if (response.ok) {
                    toast({
                        title: "Success",
                        description: "Questionnaire deleted successfully",
                        status: "success",
                        duration: 3000,
                        isClosable: true,
                    });
                    navigate('/');
                } else {
                    throw new Error('Failed to delete questionnaire');
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
        }
    };

    if (!questionnaire) {
        return <Box p={5}>Loading...</Box>;
    }

    return (
        <Box p={5} maxW="1200px" mx="auto">
            <VStack spacing={6} align="stretch">
                {isEditing ? (
                    <Grid templateColumns="repeat(2, 1fr)" gap={6}>
                        <GridItem>
                            <VStack align="stretch" spacing={4}>
                                <FormControl isRequired>
                                    <FormLabel>Title</FormLabel>
                                    <Input
                                        value={editedTitle}
                                        onChange={(e) => setEditedTitle(e.target.value)}
                                        placeholder="Enter title"
                                    />
                                </FormControl>

                                <FormControl>
                                    <FormLabel>Document Content</FormLabel>
                                    <Textarea
                                        value={editedContent}
                                        onChange={(e) => setEditedContent(e.target.value)}
                                        placeholder="Enter or paste your document content here"
                                        minHeight="400px"
                                    />
                                </FormControl>

                                <Button
                                    onClick={extractQuestions}
                                    isLoading={isExtracting}
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
                ) : (
                    <>
                        <Heading>{questionnaire.title}</Heading>
                        <Text whiteSpace="pre-wrap">{questionnaire.content}</Text>
                        <VStack align="stretch" spacing={4}>
                            <Heading size="md">Questions:</Heading>
                            {questionnaire.questions && questionnaire.questions.length > 0 ? (
                                questionnaire.questions.map((question, index) => (
                                    <Text key={index}>{index + 1}. {question}</Text>
                                ))
                            ) : (
                                <Text>No questions available.</Text>
                            )}
                        </VStack>
                    </>
                )}

                <HStack spacing={4} justify="flex-start">
                    {isEditing ? (
                        <>
                            <Button
                                colorScheme="green"
                                onClick={handleSave}
                                isLoading={isSaving}
                                loadingText="Saving..."
                            >
                                Save Changes
                            </Button>
                            <Button onClick={() => setIsEditing(false)}>Cancel</Button>
                        </>
                    ) : (
                        <>
                            <Button colorScheme="blue" onClick={() => setIsEditing(true)}>
                                Edit Questionnaire
                            </Button>
                            <Button colorScheme="red" onClick={handleDelete}>
                                Delete Questionnaire
                            </Button>
                        </>
                    )}
                    <Button as={Link} to="/">Back to Dashboard</Button>
                </HStack>

                {questionnaire.interviews && questionnaire.interviews.length > 0 && (
                    <VStack align="stretch" spacing={4}>
                        <Heading size="md">Associated Interviews:</Heading>
                        {questionnaire.interviews.map(interview => (
                            <Box key={interview.id} p={3} borderWidth={1} borderRadius="md">
                                <Link to={`/interview/${interview.id}`}>
                                    <Text fontWeight="bold">{interview.interviewee_name}</Text>
                                    <Text fontSize="sm">{new Date(interview.date).toLocaleDateString()}</Text>
                                    <Text fontSize="sm">Status: {interview.status}</Text>
                                </Link>
                            </Box>
                        ))}
                    </VStack>
                )}
            </VStack>
        </Box>
    );
}

export default ViewQuestionnaire;