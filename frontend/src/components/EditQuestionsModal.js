import React, { useState } from 'react';
import {
    Modal,
    ModalOverlay,
    ModalContent,
    ModalHeader,
    ModalFooter,
    ModalBody,
    ModalCloseButton,
    Button,
    VStack,
    Input,
    useToast,
} from '@chakra-ui/react';

const EditQuestionsModal = ({ isOpen, onClose, questions, onSave }) => {
    const [editedQuestions, setEditedQuestions] = useState(questions);
    const [isLoading, setIsLoading] = useState(false);
    const toast = useToast();

    const handleQuestionChange = (index, value) => {
        const newQuestions = [...editedQuestions];
        newQuestions[index] = value;
        setEditedQuestions(newQuestions);
    };

    const handleSave = async () => {
        if (editedQuestions.some(q => q.trim() === '')) {
            toast({
                title: "Error",
                description: "Questions cannot be empty",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
            return;
        }
        setIsLoading(true);
        try {
            await onSave(editedQuestions);
            toast({
                title: "Success",
                description: "Questions saved successfully",
                status: "success",
                duration: 3000,
                isClosable: true,
            });
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to save questions",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
        } finally {
            setIsLoading(false);
            onClose();
        }
    };

    return (
        <Modal isOpen={isOpen} onClose={onClose} closeOnOverlayClick={!isLoading}>
            <ModalOverlay />
            <ModalContent>
                <ModalHeader>Edit Questions</ModalHeader>
                <ModalCloseButton isDisabled={isLoading} />
                <ModalBody>
                    <VStack spacing={4}>
                        {editedQuestions.map((question, index) => (
                            <Input
                                key={index}
                                value={question}
                                onChange={(e) => handleQuestionChange(index, e.target.value)}
                                placeholder={`Question ${index + 1}`}
                                isDisabled={isLoading}
                            />
                        ))}
                    </VStack>
                </ModalBody>
                <ModalFooter>
                    <Button
                        colorScheme="blue"
                        mr={3}
                        onClick={handleSave}
                        isLoading={isLoading}
                        loadingText="Saving..."
                    >
                        Save
                    </Button>
                    <Button variant="ghost" onClick={onClose} isDisabled={isLoading}>
                        Cancel
                    </Button>
                </ModalFooter>
            </ModalContent>
        </Modal>
    );
};

export default EditQuestionsModal;