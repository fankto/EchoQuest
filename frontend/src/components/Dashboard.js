import React, { useState, useEffect, useCallback } from 'react';
import { Box, Heading, SimpleGrid, Button, VStack, Flex, Text, useToast, IconButton, Accordion, AccordionItem, AccordionButton, AccordionPanel, AccordionIcon, Alert, AlertIcon, AlertTitle, AlertDescription, Divider, HStack } from '@chakra-ui/react';
import { DeleteIcon } from '@chakra-ui/icons';
import { Link, useLocation } from 'react-router-dom';

function Dashboard() {
    const [questionnaires, setQuestionnaires] = useState([]);
    const toast = useToast();
    const location = useLocation();

    const fetchQuestionnaires = useCallback(async () => {
        try {
            const response = await fetch('/api/questionnaires/');
            if (response.ok) {
                const data = await response.json();
                setQuestionnaires(data);
            } else {
                throw new Error('Failed to fetch questionnaires');
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
    }, [toast]);

    useEffect(() => {
        fetchQuestionnaires();
    }, [location, fetchQuestionnaires]);  // Add location as a dependency

    const deleteQuestionnaire = async (id) => {
        try {
            const response = await fetch(`/api/questionnaires/${id}`, {
                method: 'DELETE',
            });
            if (response.ok) {
                setQuestionnaires(questionnaires.filter(questionnaire => questionnaire.id !== id));
                toast({
                    title: "Success",
                    description: "Questionnaire deleted successfully",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
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
    };

    return (
        <Box p={5}>
            <Heading mb={5}>Dashboard</Heading>

            <Alert status="info" mb={5}>
                <AlertIcon />
                <Box>
                    <AlertTitle>Welcome to the Interview Management System!</AlertTitle>
                    <AlertDescription>
                        This dashboard provides an overview of your questionnaires and associated interviews.
                        You can create new questionnaires, manage existing ones, and view interview details.
                    </AlertDescription>
                </Box>
            </Alert>

            <SimpleGrid columns={1} spacing={10}>
                <VStack align="stretch">
                    <Heading size="md" mb={3}>Getting Started</Heading>
                    <Text>
                        1. Create a new questionnaire or use an existing one.
                    </Text>
                    <Text>
                        2. Start a new interview using a questionnaire.
                    </Text>
                    <Text>
                        3. Upload audio files for the interview.
                    </Text>
                    <Text>
                        4. Process the audio, transcribe it, and generate answers.
                    </Text>
                    <Text>
                        5. Review and analyze the interview results.
                    </Text>
                </VStack>

                <VStack align="stretch">
                    <Heading size="md" mb={3}>Your Questionnaires</Heading>
                    {questionnaires.length === 0 ? (
                        <Text>You haven't created any questionnaires yet. Create your first one to get started!</Text>
                    ) : (
                        <Accordion allowMultiple>
                            {questionnaires.map(questionnaire => (
                                <AccordionItem key={questionnaire.id}>
                                    <AccordionButton>
                                        <Box flex="1" textAlign="left">
                                            <Text fontWeight="bold">{questionnaire.title}</Text>
                                            <Text fontSize="sm">Interviews: {questionnaire.interviews ? questionnaire.interviews.length : 0}</Text>
                                        </Box>
                                        <AccordionIcon />
                                    </AccordionButton>
                                    <AccordionPanel pb={4}>
                                        {questionnaire.interviews && questionnaire.interviews.length > 0 ? (
                                            questionnaire.interviews.map(interview => (
                                                <Box key={interview.id} p={2} borderWidth={1} borderRadius="md" mb={2}>
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
                                        <Flex justifyContent="space-between" alignItems="center" mt={3}>
                                            <Button as={Link} to={`/view-questionnaire/${questionnaire.id}`} colorScheme="blue" size="sm">
                                                View Questionnaire
                                            </Button>
                                            <IconButton
                                                icon={<DeleteIcon />}
                                                onClick={() => deleteQuestionnaire(questionnaire.id)}
                                                aria-label="Delete questionnaire"
                                                size="sm"
                                                colorScheme="red"
                                            />
                                        </Flex>
                                    </AccordionPanel>
                                </AccordionItem>
                            ))}
                        </Accordion>
                    )}
                </VStack>
            </SimpleGrid>

            <Divider my={8} />

            <Box>
                <Heading size="md" mb={4}>Quick Actions</Heading>
                <HStack spacing={4} justify="center">
                    <Button as={Link} to="/questionnaire" colorScheme="green" size="md" width="200px">
                        New Questionnaire
                    </Button>
                    <Button as={Link} to="/create-interview" colorScheme="blue" size="md" width="200px">
                        New Interview
                    </Button>
                    <Button as={Link} to="/all-interviews" colorScheme="purple" size="md" width="200px">
                        View All Interviews
                    </Button>
                </HStack>
            </Box>
        </Box>
    );
}

export default Dashboard;