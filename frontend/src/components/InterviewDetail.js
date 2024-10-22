import React, { useState, useEffect, useCallback } from 'react';
import { Box, VStack, Heading, Text, Button, Progress, useToast, List, ListItem, IconButton, NumberInput, NumberInputField, NumberInputStepper, NumberIncrementStepper, NumberDecrementStepper, Flex, Select } from '@chakra-ui/react';
import { DeleteIcon } from '@chakra-ui/icons';
import { FaPlay, FaPause } from 'react-icons/fa'
import { useParams } from 'react-router-dom';
import {
    Accordion,
    AccordionItem,
    AccordionButton,
    AccordionPanel,
    AccordionIcon,
} from '@chakra-ui/react';

function AudioPlayer({ filename }) {
    const [audio] = useState(new Audio(`/api/interviews/audio/${filename}`));
    const [playing, setPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);

    useEffect(() => {
        audio.addEventListener('loadedmetadata', () => setDuration(audio.duration));
        audio.addEventListener('timeupdate', () => setCurrentTime(audio.currentTime));
        return () => {
            audio.removeEventListener('loadedmetadata', () => setDuration(audio.duration));
            audio.removeEventListener('timeupdate', () => setCurrentTime(audio.currentTime));
        };
    }, [audio]);

    const togglePlayPause = () => {
        if (playing) {
            audio.pause();
        } else {
            audio.play();
        }
        setPlaying(!playing);
    };

    const handleSliderChange = (event) => {
        const time = parseFloat(event.target.value);
        audio.currentTime = time;
        setCurrentTime(time);
    };

    return (
        <Box>
            <Text>{filename}</Text>
            <IconButton icon={playing ? <FaPause /> : <FaPlay />} onClick={togglePlayPause} />
            <input
                type="range"
                min={0}
                max={duration}
                value={currentTime}
                onChange={handleSliderChange}
            />
            <Text>{formatTime(currentTime)} / {formatTime(duration)}</Text>
        </Box>
    );
}

function formatTime(time) {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function InterviewDetail() {
    const { id } = useParams();
    const [interview, setInterview] = useState(null);
    const [newAudioFile, setNewAudioFile] = useState(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [answerProgress, setAnswerProgress] = useState(0);
    const [isTranscribing, setIsTranscribing] = useState(false);
    const [isGeneratingAnswers, setIsGeneratingAnswers] = useState(false);
    const [isPolling, setIsPolling] = useState(false);
    const [minSpeakers, setMinSpeakers] = useState('');
    const [maxSpeakers, setMaxSpeakers] = useState('');
    const [questionnaires, setQuestionnaires] = useState([]);
    const [selectedQuestionnaireId, setSelectedQuestionnaireId] = useState(null);
    const toast = useToast();

    const fetchInterview = useCallback(async () => {
        setIsLoading(true);
        try {
            const response = await fetch(`/api/interviews/${id}`);
            if (response.ok) {
                const data = await response.json();
                setInterview(data);
            } else {
                throw new Error('Failed to fetch interview details');
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
            setIsLoading(false);
        }
    }, [id, toast]);

    useEffect(() => {
        fetchInterview();
    }, [fetchInterview]);

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

    useEffect(() => {
        if (interview && interview.questionnaire) {
            setSelectedQuestionnaireId(interview.questionnaire.id);
        }
    }, [interview]);

    const handleQuestionnaireChange = async (e) => {
        const newQuestionnaireId = parseInt(e.target.value);
        setSelectedQuestionnaireId(newQuestionnaireId);

        try {
            const response = await fetch(`/api/interviews/${id}/update-questionnaire`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ questionnaire_id: newQuestionnaireId }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Questionnaire updated successfully",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                fetchInterview();
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
        }
    };

    const handleFileChange = (event) => {
        setNewAudioFile(event.target.files[0]);
    };

    const addAudioFile = async () => {
        if (!newAudioFile) return;

        const formData = new FormData();
        formData.append('file', newAudioFile);

        try {
            const response = await fetch(`/api/interviews/${id}/add-audio`, {
                method: 'POST',
                body: formData,
            });
            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Audio file added successfully",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                setNewAudioFile(null);
                fetchInterview();
            } else {
                throw new Error('Failed to add audio file');
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

    const removeAudioFile = async (filename) => {
        try {
            const response = await fetch(`/api/interviews/${id}/remove-audio`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ filename }),
            });
            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Audio file removed successfully",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                fetchInterview();
            } else {
                throw new Error('Failed to remove audio file');
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

    const processAudio = async () => {
        setIsProcessing(true);
        try {
            const response = await fetch(`/api/interviews/process/${id}`, { method: 'POST' });
            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Audio processing started",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                checkProcessingStatus();
            } else {
                throw new Error('Failed to start audio processing');
            }
        } catch (error) {
            toast({
                title: "Error",
                description: error.message,
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            setIsProcessing(false);
        }
    };

    const checkProcessingStatus = () => {
        const intervalId = setInterval(async () => {
            const response = await fetch(`/api/interviews/${id}`);
            const data = await response.json();
            if (data.status === 'processed' || data.status === 'error') {
                clearInterval(intervalId);
                setIsProcessing(false);
                fetchInterview();
            }
        }, 5000);
    };

    const removeProcessedAudioFile = async (filename) => {
        try {
            const response = await fetch(`/api/interviews/${id}/remove-processed-audio`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ filename }),
            });
            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Processed audio file removed successfully",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                fetchInterview();
            } else {
                throw new Error('Failed to remove processed audio file');
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

    const transcribeAudio = async () => {
        if (!interview.processed_filenames || interview.processed_filenames.length === 0) {
            toast({
                title: "Error",
                description: "Please process the audio files before transcribing.",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            return;
        }

        setIsTranscribing(true);
        try {
            const response = await fetch(`/api/interviews/transcribe/${id}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    min_speakers: minSpeakers ? parseInt(minSpeakers) : null,
                    max_speakers: maxSpeakers ? parseInt(maxSpeakers) : null,
                }),
            });
            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Transcription started",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                checkTranscriptionStatus();
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to start transcription');
            }
        } catch (error) {
            toast({
                title: "Error",
                description: error.message,
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            setIsTranscribing(false);
        }
    };

    const checkTranscriptionStatus = () => {
        const intervalId = setInterval(async () => {
            const response = await fetch(`/api/interviews/${id}`);
            const data = await response.json();
            if (data.status === 'transcribed' || data.status === 'error') {
                clearInterval(intervalId);
                setIsTranscribing(false);
                fetchInterview();
            }
        }, 5000);
    };

    const generateAnswers = async () => {
        if (!interview.merged_transcription) {
            toast({
                title: "Error",
                description: "Please transcribe the audio before generating answers.",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            return;
        }

        if (!selectedQuestionnaireId) {
            toast({
                title: "Error",
                description: "Please select a questionnaire before generating answers.",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            return;
        }

        setIsGeneratingAnswers(true);
        try {
            const response = await fetch(`/api/interviews/generate-answers/${id}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    questionnaire_id: selectedQuestionnaireId
                }),
            });
            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Answer generation started",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                setIsPolling(true);
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to start answer generation');
            }
        } catch (error) {
            toast({
                title: "Error",
                description: error.message,
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            setIsGeneratingAnswers(false);
        }
    };

    const checkAnswerProgress = useCallback(async () => {
        if (!isPolling) return;

        try {
            const response = await fetch(`/api/interviews/answer-progress/${id}`);
            const data = await response.json();
            setAnswerProgress(data.progress);

            if (data.status === 'answered' || data.status === 'error') {
                setIsPolling(false);
                setIsGeneratingAnswers(false);
                if (data.status === 'answered') {
                    fetchInterview();
                } else {
                    toast({
                        title: "Error",
                        description: data.error_message || "An error occurred during answer generation",
                        status: "error",
                        duration: 5000,
                        isClosable: true,
                    });
                }
            }
        } catch (error) {
            console.error("Error checking answer progress:", error);
            setIsPolling(false);
            setIsGeneratingAnswers(false);
        }
    }, [id, isPolling, toast, fetchInterview]);

    useEffect(() => {
        let intervalId;
        if (isPolling) {
            intervalId = setInterval(checkAnswerProgress, 5000);
        }
        return () => clearInterval(intervalId);
    }, [isPolling, checkAnswerProgress]);

    if (isLoading) {
        return <Box>Loading...</Box>;
    }

    if (!interview) {
        return <Box>Interview not found</Box>;
    }

    return (
        <Box p={5}>
            <Heading mb={5}>Interview Details</Heading>
            <VStack align="start" spacing={4}>
                <Text><strong>Interviewee:</strong> {interview.interviewee_name}</Text>
                <Text><strong>Date:</strong> {new Date(interview.date).toLocaleString()}</Text>
                <Text><strong>Status:</strong> {interview.status}</Text>

                <Box>
                    <Heading size="md">Questionnaire</Heading>
                    <Select
                        value={selectedQuestionnaireId || ''}
                        onChange={handleQuestionnaireChange}
                        placeholder="Select questionnaire"
                    >
                        {questionnaires.map((q) => (
                            <option key={q.id} value={q.id}>
                                {q.title}
                            </option>
                        ))}
                    </Select>
                </Box>

                <Accordion allowMultiple width="100%">
                    <AccordionItem>
                        <AccordionButton>
                            <Box flex="1" textAlign="left">
                                <Heading size="md">Audio Files</Heading>
                            </Box>
                            <AccordionIcon />
                        </AccordionButton>
                        <AccordionPanel pb={4}>
                            {interview.original_filenames && interview.original_filenames.length > 0 ? (
                                <List spacing={3}>
                                    {interview.original_filenames.map((filename, index) => (
                                        <ListItem key={index} display="flex" justifyContent="space-between" alignItems="center">
                                            <AudioPlayer filename={filename} />
                                            <IconButton
                                                icon={<DeleteIcon />}
                                                onClick={() => removeAudioFile(filename)}
                                                aria-label="Remove file"
                                            />
                                        </ListItem>
                                    ))}
                                </List>
                            ) : (
                                <Text>No audio files uploaded yet.</Text>
                            )}
                            <input type="file" onChange={handleFileChange} accept="audio/*" style={{ marginTop: '10px' }} />
                            <Button onClick={addAudioFile} isDisabled={!newAudioFile} mt={2}>
                                Add Audio File
                            </Button>
                        </AccordionPanel>
                    </AccordionItem>

                    <AccordionItem>
                        <AccordionButton>
                            <Box flex="1" textAlign="left">
                                <Heading size="md">Processed Audio Files</Heading>
                            </Box>
                            <AccordionIcon />
                        </AccordionButton>
                        <AccordionPanel pb={4}>
                            {interview.processed_filenames && interview.processed_filenames.length > 0 ? (
                                <List spacing={3}>
                                    {interview.processed_filenames.map((filename, index) => (
                                        <ListItem key={index} display="flex" justifyContent="space-between" alignItems="center">
                                            <AudioPlayer filename={filename} />
                                            <IconButton
                                                icon={<DeleteIcon />}
                                                onClick={() => removeProcessedAudioFile(filename)}
                                                aria-label="Remove processed file"
                                            />
                                        </ListItem>
                                    ))}
                                </List>
                            ) : (
                                <Text>No processed audio files yet.</Text>
                            )}
                            <Box mt={4}>
                                <Button
                                    onClick={processAudio}
                                    isLoading={isProcessing}
                                    loadingText="Processing"
                                    width="200px"
                                >
                                    Process Audio
                                </Button>
                            </Box>

                        </AccordionPanel>
                    </AccordionItem>

                    <AccordionItem>
                        <AccordionButton>
                            <Box flex="1" textAlign="left">
                                <Heading size="md">Transcription</Heading>
                            </Box>
                            <AccordionIcon />
                        </AccordionButton>
                        <AccordionPanel pb={4}>
                            <Box mt={4}>
                                <Heading size="sm">Transcription Settings</Heading>
                                <Flex mt={2}>
                                    <Box mr={4}>
                                        <Text>Min Speakers:</Text>
                                        <NumberInput
                                            min={1}
                                            max={10}
                                            value={minSpeakers}
                                            onChange={(valueString) => setMinSpeakers(valueString)}
                                        >
                                            <NumberInputField />
                                            <NumberInputStepper>
                                                <NumberIncrementStepper />
                                                <NumberDecrementStepper />
                                            </NumberInputStepper>
                                        </NumberInput>
                                    </Box>
                                    <Box>
                                        <Text>Max Speakers:</Text>
                                        <NumberInput
                                            min={1}
                                            max={10}
                                            value={maxSpeakers}
                                            onChange={(valueString) => setMaxSpeakers(valueString)}
                                        >
                                            <NumberInputField />
                                            <NumberInputStepper>
                                                <NumberIncrementStepper />
                                                <NumberDecrementStepper />
                                            </NumberInputStepper>
                                        </NumberInput>
                                    </Box>
                                </Flex>
                            </Box>
                            <Box mt={4}>
                                <Button
                                    onClick={transcribeAudio}
                                    isLoading={isTranscribing}
                                    loadingText="Transcribing"
                                    isDisabled={isTranscribing || !interview.processed_filenames || interview.processed_filenames.length === 0}
                                    width="200px"
                                >
                                    Transcribe
                                </Button>
                            </Box>

                            {interview.merged_transcription && (
                                <Box mt={4}>
                                    <Heading size="sm">Transcription Result</Heading>
                                    <Box w="100%" maxH="300px" overflowY="auto" mt={2}>
                                        <Text whiteSpace="pre-wrap">
                                            {interview.merged_transcription}
                                        </Text>
                                    </Box>
                                </Box>
                            )}
                        </AccordionPanel>
                    </AccordionItem>

                    <AccordionItem>
                        <AccordionButton>
                            <Box flex="1" textAlign="left">
                                <Heading size="md">Generated Answers</Heading>
                            </Box>
                            <AccordionIcon />
                        </AccordionButton>
                        <AccordionPanel pb={4}>
                            <Box mt={4}>
                                <Button
                                    onClick={generateAnswers}
                                    isLoading={isGeneratingAnswers}
                                    loadingText="Generating Answers"
                                    isDisabled={isGeneratingAnswers || !interview.merged_transcription || !selectedQuestionnaireId}
                                    width="200px"
                                >
                                    Generate Answers
                                </Button>
                            </Box>
                            {answerProgress > 0 && (
                                <Box mb={4}>
                                    <Text>Answer Generation Progress:</Text>
                                    <Progress value={answerProgress} />
                                </Box>
                            )}
                            {interview.generated_answers && Object.entries(interview.generated_answers).length > 0 && (
                                <Box>
                                    <Heading size="sm">Generated Answers</Heading>
                                    {Object.entries(interview.generated_answers).map(([question, answer], index) => (
                                        <Box key={index} mt={2}>
                                            <Text fontWeight="bold">{question}</Text>
                                            <Text>{answer}</Text>
                                        </Box>
                                    ))}
                                </Box>
                            )}
                        </AccordionPanel>
                    </AccordionItem>
                </Accordion>
            </VStack>
        </Box>
    );
}

export default InterviewDetail;