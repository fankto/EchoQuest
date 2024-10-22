import React, { useState, useEffect } from 'react';
import { Box, Heading, VStack, Text, Button, useToast, Textarea, Input, HStack, OrderedList, ListItem } from '@chakra-ui/react';
import { useParams, Link, useNavigate } from 'react-router-dom';

function ViewQuestionnaire() {
    const { id } = useParams();
    const [questionnaire, setQuestionnaire] = useState(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editedTitle, setEditedTitle] = useState('');
    const [editedContent, setEditedContent] = useState('');
    const [isSaving, setIsSaving] = useState(false);
    const toast = useToast();
    const navigate = useNavigate();

    useEffect(() => {
        fetchQuestionnaire();
    }, [id]);

    const fetchQuestionnaire = async () => {
        try {
            const response = await fetch(`/api/questionnaires/${id}`);
            if (response.ok) {
                const data = await response.json();
                setQuestionnaire(data);
                setEditedTitle(data.title);
                setEditedContent(data.content);
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

    const handleEdit = () => {
        setIsEditing(true);
    };

    const handleCancel = () => {
        setIsEditing(false);
        setEditedTitle(questionnaire.title);
        setEditedContent(questionnaire.content);
    };

    const handleSave = async () => {
        setIsSaving(true);
        try {
            const formData = new FormData();
            formData.append('title', editedTitle);
            formData.append('content', editedContent);

            const response = await fetch(`/api/questionnaires/${id}`, {
                method: 'PUT',
                body: formData,
            });

            if (response.ok) {
                const updatedQuestionnaire = await response.json();
                setQuestionnaire(updatedQuestionnaire);
                setIsEditing(false);
                toast({
                    title: "Success",
                    description: "Questionnaire updated successfully",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
            } else {
                throw new Error('Failed to update questionnaire');
            }
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
        return <Box>Loading...</Box>;
    }

    return (
        <Box p={5}>
            {isEditing ? (
                <VStack align="stretch" spacing={4}>
                    <Input
                        value={editedTitle}
                        onChange={(e) => setEditedTitle(e.target.value)}
                        placeholder="Questionnaire Title"
                    />
                    <Textarea
                        value={editedContent}
                        onChange={(e) => setEditedContent(e.target.value)}
                        placeholder="Questionnaire Content"
                        minHeight="200px"
                    />
                    <Button
                        colorScheme="blue"
                        onClick={handleSave}
                        isLoading={isSaving}
                        loadingText="Saving..."
                    >
                        Save
                    </Button>
                    <Button onClick={handleCancel} isDisabled={isSaving}>Cancel</Button>
                </VStack>
            ) : (
                <>
                    <Heading mb={5}>{questionnaire.title}</Heading>
                    <VStack align="stretch" spacing={4} mb={4}>
                        <Heading size="md">Extracted Questions:</Heading>
                        {questionnaire.questions && questionnaire.questions.length > 0 ? (
                            <OrderedList spacing={2}>
                                {questionnaire.questions.map((question, index) => (
                                    <ListItem key={index} ml={4}>
                                        {question}
                                    </ListItem>
                                ))}
                            </OrderedList>
                        ) : (
                            <Text>No questions extracted from this questionnaire.</Text>
                        )}
                    </VStack>
                    <VStack align="stretch" spacing={4}>
                        <Heading size="md">Associated Interviews:</Heading>
                        {questionnaire.interviews && questionnaire.interviews.length > 0 ? (
                            questionnaire.interviews.map(interview => (
                                <Box key={interview.id} p={3} borderWidth={1} borderRadius="md">
                                    <Link to={`/interview/${interview.id}`}>
                                        <Text fontWeight="bold">{interview.interviewee_name}</Text>
                                        <Text fontSize="sm">{new Date(interview.date).toLocaleDateString()}</Text>
                                        <Text fontSize="sm">Status: {interview.status}</Text>
                                    </Link>
                                </Box>
                            ))
                        ) : (
                            <Text>No interviews associated with this questionnaire.</Text>
                        )}
                    </VStack>
                </>
            )}
            <HStack spacing={4} mt={4}>
                <Button colorScheme="blue" onClick={handleEdit} width="200px">Edit Questionnaire</Button>
                <Button colorScheme="red" onClick={handleDelete} width="200px">Delete Questionnaire</Button>
            </HStack>
            <Button as={Link} to="/" mt={8} width="200px">Back to Dashboard</Button>
        </Box>
    );
}

export default ViewQuestionnaire;