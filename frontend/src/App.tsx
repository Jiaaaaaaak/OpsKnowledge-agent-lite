import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ProjectProvider } from './context/ProjectContext';
import AppLayout from './components/layout/AppLayout';
import ProjectPage from './pages/ProjectPage';
import DashboardPage from './pages/DashboardPage';
import ChatPage from './pages/ChatPage';
import DocumentsPage from './pages/DocumentsPage';
import AnalysisPage from './pages/AnalysisPage';
import AgentRunsPage from './pages/AgentRunsPage';
import SystemStatusPage from './pages/SystemStatusPage';

function App() {
  return (
    <ProjectProvider>
      <Router>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Navigate to="/projects" replace />} />
            <Route path="projects" element={<ProjectPage />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="documents" element={<DocumentsPage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="analysis" element={<AnalysisPage />} />
            <Route path="agent-runs" element={<AgentRunsPage />} />
            <Route path="status" element={<SystemStatusPage />} />
          </Route>
        </Routes>
      </Router>
    </ProjectProvider>
  );
}

export default App;