import React, {useCallback, useEffect, useState} from 'react';
import {
    Box,
    Button,
    Heading,
    IconButton,
    Input,
    List,
    ListItem,
    Select,
    Text,
    useToast,
    VStack
} from '@chakra-ui/react';
import {DeleteIcon} from '@chakra-ui/icons';
import {useNavigate} from 'react-router-dom';

function InterviewCreation() {
    const [intervieweeName, setIntervieweeName] = useState('');
    const [selectedQuestionnaire, setSelectedQuestionnaire] = useState('');
    const [audioFiles, setAudioFiles] = useState([]);
    const [questionnaires, setQuestionnaires] = useState([]);
    const toast = useToast();
    const navigate = useNavigate();

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
    }, [fetchQuestionnaires]);

    const handleFileChange = (event) => {
        setAudioFiles([...audioFiles, ...Array.from(event.target.files)]);
    };

    const removeFile = (index) => {
        setAudioFiles(audioFiles.filter((_, i) => i !== index));
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!intervieweeName || !selectedQuestionnaire || audioFiles.length === 0) {
            toast({
                title: "Error",
                description: "Please fill all fields and upload at least one audio file.",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            return;
        }

        const formData = new FormData();
        formData.append('interviewee_name', intervieweeName);
        formData.append('questionnaire_id', selectedQuestionnaire);
        formData.append('date', new Date().toISOString());
        formData.append('location', 'N/A'); // You might want to add a location field in the form
        audioFiles.forEach((file, index) => {
            formData.append(`files`, file);
        });

        try {
            const response = await fetch('/api/interviews/upload', {
                method: 'POST',
                body: formData,
            });
            if (response.ok) {
                const data = await response.json();
                toast({
                    title: "Success",
                    description: "Interview created successfully",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                navigate(`/interview/${data.id}`);
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to create interview');
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
            <Heading mb={5}>Create New Interview</Heading>
            <form onSubmit={handleSubmit}>
                <VStack spacing={4} align="stretch">
                    <Input
                        placeholder="Interviewee Name"
                        value={intervieweeName}
                        onChange={(e) => setIntervieweeName(e.target.value)}
                    />
                    <Select
                        placeholder="Select Questionnaire"
                        value={selectedQuestionnaire}
                        onChange={(e) => setSelectedQuestionnaire(e.target.value)}
                    >
                        {questionnaires.map(q => (
                            <option key={q.id} value={q.id}>{q.title}</option>
                        ))}
                    </Select>
                    <Input
                        type="file"
                        accept="audio/*"
                        multiple
                        onChange={handleFileChange}
                    />
                    <List spacing={3}>
                        {audioFiles.map((file, index) => (
                            <ListItem key={index} display="flex" justifyContent="space-between" alignItems="center">
                                <Text>{file.name}</Text>
                                <IconButton
                                    icon={<DeleteIcon/>}
                                    onClick={() => removeFile(index)}
                                    aria-label="Remove file"
                                />
                            </ListItem>
                        ))}
                    </List>
                    <Button type="submit" colorScheme="blue">Create Interview</Button>
                </VStack>
            </form>
        </Box>
    );
}

export default InterviewCreation;