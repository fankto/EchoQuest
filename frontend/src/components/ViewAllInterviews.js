import React, { useState, useEffect, useCallback } from 'react';
import { Box, Heading, VStack, Text, Button, useToast, IconButton, HStack } from '@chakra-ui/react';
import { DeleteIcon } from '@chakra-ui/icons';
import { Link } from 'react-router-dom';

function ViewAllInterviews() {
    const [interviews, setInterviews] = useState([]);
    const toast = useToast();

    const fetchInterviews = useCallback(async () => {
        try {
            const response = await fetch('/api/interviews/');
            if (response.ok) {
                const data = await response.json();
                setInterviews(data);
            } else {
                throw new Error('Failed to fetch interviews');
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
        fetchInterviews();
    }, [fetchInterviews]);

    const deleteInterview = async (id) => {
        try {
            const response = await fetch(`/api/interviews/${id}`, {
                method: 'DELETE',
            });
            if (response.ok) {
                setInterviews(interviews.filter(interview => interview.id !== id));
                toast({
                    title: "Success",
                    description: "Interview deleted successfully",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
            } else {
                throw new Error('Failed to delete interview');
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
            <Heading mb={5}>All Interviews</Heading>
            <VStack align="stretch" spacing={4}>
                {interviews.map(interview => (
                    <HStack key={interview.id} p={3} borderWidth={1} borderRadius="md" justifyContent="space-between">
                        <Box>
                            <Link to={`/interview/${interview.id}`}>
                                <Text fontWeight="bold">{interview.interviewee_name}</Text>
                                <Text fontSize="sm">{new Date(interview.date).toLocaleDateString()}</Text>
                                <Text fontSize="sm">Status: {interview.status}</Text>
                            </Link>
                        </Box>
                        <IconButton
                            icon={<DeleteIcon />}
                            onClick={() => deleteInterview(interview.id)}
                            aria-label="Delete interview"
                            colorScheme="red"
                        />
                    </HStack>
                ))}
            </VStack>
            <Button as={Link} to="/" mt={8} width="200px">Back to Dashboard</Button>
        </Box>
    );
}

export default ViewAllInterviews;