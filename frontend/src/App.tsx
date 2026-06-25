import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ProjectProvider } from './context/ProjectContext';
import AppLayout from './components/layout/AppLayout';
import ProjectPage from './pages/ProjectPage';
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
            <Route path="document-upload" element={<DocumentUploadPage />} />
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