import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProjectProvider } from './context/ProjectContext';
import ProtectedRoute from './components/auth/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import AppLayout from './components/layout/AppLayout';
import ProjectPage from './pages/ProjectPage';
import AgentRunsPage from './pages/AgentRunsPage';
import SystemStatusPage from './pages/SystemStatusPage';
import KnowledgeWorkflowPage from './pages/KnowledgeWorkflowPage';

function App() {
  return (
    <AuthProvider>
      <ProjectProvider>
        <Router>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/projects" replace />} />
              <Route path="projects" element={<ProjectPage />} />
              <Route path="document-upload" element={<Navigate to="/knowledge/workflow" replace />} />
              <Route path="knowledge/workflow" element={<KnowledgeWorkflowPage />} />
              <Route path="agent-runs" element={<AgentRunsPage />} />
              <Route path="status" element={<SystemStatusPage />} />
            </Route>
          </Routes>
        </Router>
      </ProjectProvider>
    </AuthProvider>
  );
}

export default App;
