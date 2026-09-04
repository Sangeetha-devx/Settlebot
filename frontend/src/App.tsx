import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Reconciliation from './pages/Reconciliation';
import Exceptions from './pages/Exceptions';
import Settlements from './pages/Settlements';
import Forecast from './pages/Forecast';
import AskSettleBot from './pages/AskSettleBot';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/" replace /> : <Login />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/reconciliation" element={<Reconciliation />} />
        <Route path="/exceptions" element={<Exceptions />} />
        <Route path="/settlements" element={<Settlements />} />
        <Route path="/forecast" element={<Forecast />} />
        <Route path="/ask" element={<AskSettleBot />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
