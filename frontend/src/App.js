// frontend/src/App.js
import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import { ChakraProvider, Box, Flex, Container } from '@chakra-ui/react';

import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import InterviewDetail from './components/InterviewDetail';
import InterviewCreation from './components/InterviewCreation';
import QuestionnaireEditor from './components/QuestionnaireEditor';
import ViewQuestionnaire from './components/ViewQuestionnaire';
import ViewAllInterviews from './components/ViewAllInterviews';

function App() {
    return (
        <ChakraProvider>
            <Router>
                <Box bg="gray.50" minHeight="100vh">
                    <Container maxW="container.xl" px={4} py={5}>
                        <Flex gap={4}>
                            <Box w="200px" bg="white" borderRadius="md" boxShadow="sm" height="fit-content">
                                <Sidebar />
                            </Box>
                            <Box flex={1} bg="white" p={5} borderRadius="md" boxShadow="sm">
                                <Routes>
                                    <Route path="/" element={<Dashboard />} />
                                    <Route path="/interview/:id" element={<InterviewDetail />} />
                                    <Route path="/create-interview" element={<InterviewCreation />} />
                                    <Route path="/questionnaire/:id?" element={<QuestionnaireEditor />} />
                                    <Route path="/view-questionnaire/:id" element={<ViewQuestionnaire />} />
                                    <Route path="/all-interviews" element={<ViewAllInterviews />} />
                                </Routes>
                            </Box>
                        </Flex>
                    </Container>
                </Box>
            </Router>
        </ChakraProvider>
    );
}

export default App;