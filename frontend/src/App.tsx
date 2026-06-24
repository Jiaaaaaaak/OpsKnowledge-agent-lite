import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ProjectProvider } from './context/ProjectContext';
import AppLayout from './components/layout/AppLayout';
import ProjectPage from './pages/ProjectPage';
import ChatPage from './pages/ChatPage';
import DocumentUploadPage from './pages/DocumentUploadPage';
import AgentRunsPage from './pages/AgentRunsPage';
import SystemStatusPage from './pages/SystemStatusPage';
import KnowledgeWorkflowPage from './pages/KnowledgeWorkflowPage';

function App() {
  return (
    <ProjectProvider>
      <Router>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Navigate to="/projects" replace />} />
            <Route path="projects" element={<ProjectPage />} />
            <Route path="dashboard" element={<Navigate to="/knowledge/workflow" replace />} />
            <Route path="incident-upload" element={<Navigate to="/knowledge/workflow" replace />} />
            <Route path="document-upload" element={<DocumentUploadPage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="analysis" element={<Navigate to="/knowledge/workflow" replace />} />
            <Route path="insights/workflow" element={<Navigate to="/knowledge/workflow" replace />} />
            <Route path="analysis/result/:agentRunId" element={<Navigate to="/knowledge/workflow" replace />} />
            <Route path="knowledge/workflow" element={<KnowledgeWorkflowPage />} />
            <Route path="agent-runs" element={<AgentRunsPage />} />
            <Route path="status" element={<SystemStatusPage />} />
          </Route>
        </Routes>
      </Router>
    </ProjectProvider>
  );
}

export default App;