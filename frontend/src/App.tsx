import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { SessionProvider } from "@/store/sessionContext";
import UploadPage from "@/pages/UploadPage";
import AnalyzingPage from "@/pages/AnalyzingPage";
import ResultPage from "@/pages/ResultPage";

export default function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/analyzing" element={<AnalyzingPage />} />
          <Route path="/result" element={<ResultPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  );
}
