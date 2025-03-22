import React from 'react';
import { Box, VStack, Link } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

function Sidebar() {
    return (
        <Box width="200px" bg="gray.100" height="100vh" p={4}>
            <VStack align="stretch" spacing={4}>
                <Link as={RouterLink} to="/">Dashboard</Link>
                <Link as={RouterLink} to="/create-interview">New Interview</Link>
                <Link as={RouterLink} to="/questionnaire">New Questionnaire</Link>
                <Link as={RouterLink} to="/all-interviews">View All Interviews</Link>
            </VStack>
        </Box>
    );
}

export default Sidebar;