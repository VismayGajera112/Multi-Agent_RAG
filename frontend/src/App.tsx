import { Header } from "./components/Header";
import { MetricsBar } from "./components/MetricsBar";
import { ChatWindow } from "./components/chat/ChatWindow";
import { UploadPanel } from "./components/upload/UploadPanel";
import { useDocumentStore } from "./store/documentStore";

export default function App() {
  const hasDocuments = useDocumentStore((s) =>
    s.items.some((i) => i.state === "processed"),
  );

  return (
    <div className="flex h-full flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-brand-600 focus:px-3 focus:py-2 focus:text-sm focus:text-white"
      >
        Skip to content
      </a>
      <Header />
      <main
        id="main"
        className="mx-auto w-full max-w-7xl flex-1 px-6 py-6"
      >
        <div className="grid grid-cols-1 gap-6 lg:h-[calc(100vh-11.5rem)] lg:grid-cols-2">
          <UploadPanel />
          <ChatWindow hasDocuments={hasDocuments} />
        </div>
      </main>
      <MetricsBar />
    </div>
  );
}
