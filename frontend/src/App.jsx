import { SessionProvider, useSession } from "./context/SessionContext";
import LoginForm from "./components/LoginForm";
import ChatPage from "./pages/ChatPage";

function AppShell() {
  const { isAuthenticated } = useSession();
  if (!isAuthenticated) {
    return (
      <div className="auth-screen">
        <LoginForm />
      </div>
    );
  }
  return <ChatPage />;
}

export default function App() {
  return (
    <SessionProvider>
      <AppShell />
    </SessionProvider>
  );
}
