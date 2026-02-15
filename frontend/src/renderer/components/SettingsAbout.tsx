import { useEffect, useState } from "react";
import { Versions } from "../../types/interfaces";
import { klippyApi } from "../klippyApi";

export const SettingsAbout: React.FC = () => {
  const [versions, setVersions] = useState<Partial<Versions>>({});

  useEffect(() => {
    klippyApi.getVersions().then((versions) => {
      setVersions(versions);
    });
  }, []);

  return (
    <div>
      <h1>About Klippy 📎</h1>
      <p style={{ fontStyle: "italic", marginBottom: "12px" }}>
        Paperclips Organized Your Documents Since 1867.<br/>Now They Understand Them.
      </p>
      <fieldset>
        <legend>What is Klippy?</legend>
        <p>
          <strong>Klippy</strong> is a <strong>local-first AI assistant</strong> that remembers everything. It combines:
        </p>
        <ul style={{ marginTop: "8px", marginBottom: "8px" }}>
          <li>🔍 <strong>Multimodal RAG</strong> – Search across text, images, and audio with one query</li>
          <li>🧠 <strong>Knowledge Graph Reasoning</strong> – Neo4j-powered ontological reasoning for complex queries</li>
          <li>⚡ <strong>Prompt Chaining</strong> – Google ADK agents orchestrate multi-step reasoning pipelines</li>
          <li>💾 <strong>Personal Memory</strong> – Your data stays local, your assistant gets smarter</li>
        </ul>
        <p style={{ marginTop: "8px", fontSize: "0.9em" }}>
          <strong>Architecture Philosophy:</strong> <em>"Graph-as-Brain, LLM-as-Mouth"</em> – All reasoning is pre-computed via deterministic graph logic. The LLM only narrates the answer. This allows sub-4B models like Qwen2.5:3b to perform like much larger models.
        </p>
      </fieldset>
      <fieldset>
        <legend>Version Information</legend>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <div>
            <strong>Klippy:</strong> <code>{versions.klippy || "Unknown"}</code>
          </div>
          <div>
            <strong>Electron:</strong> <code>{versions.electron || "Unknown"}</code>
          </div>
          <div>
            <strong>Node-llama-cpp:</strong> <code>{versions.nodeLlamaCpp || "Unknown"}</code>
          </div>
        </div>
      </fieldset>
      <fieldset>
        <legend>Tech Stack</legend>
        <p>
          <strong>Backend:</strong> FastAPI, Python 3.12+, Pydantic<br/>
          <strong>Frontend:</strong> Electron, React, TypeScript, Vite<br/>
          <strong>Vector DB:</strong> Qdrant (HNSW indexing)<br/>
          <strong>Graph DB:</strong> Neo4j (Cypher queries)<br/>
          <strong>LLM:</strong> Ollama (Qwen2.5:3b / Llama3.2)<br/>
          <strong>Agents:</strong> Google ADK, LiteLLM<br/>
          <strong>Embeddings:</strong> MiniLM-L6-v2 (384-dim)<br/>
          <strong>Vision:</strong> BLIP (image captioning), Tesseract (OCR)<br/>
          <strong>Speech:</strong> Whisper (speech-to-text)<br/>
          <strong>NLP:</strong> spaCy (NER, relationship extraction)
        </p>
      </fieldset>
      <h3>Hackathon Project</h3>
      <p>
        This project was built for the <strong>AI-Minds Hackathon 2026</strong>. It demonstrates how combining knowledge graphs with small language models can create powerful local-first AI assistants.
      </p>
      <p style={{ fontSize: "0.9em", marginTop: "12px" }}>
        The character design is inspired by Microsoft's Clippy from Office 1997, designed by illustrator{" "}
        <a href="https://www.kevanatteberry.com/" target="_blank">
          Kevan Atteberry
        </a>
        . This project is not affiliated with Microsoft.
      </p>
      <p style={{ fontSize: "0.9em", marginTop: "8px" }}>
        <strong>License:</strong> MIT – See the{" "}
        <a href="https://github.com/Rayen-Hamza/AI-Minds-Hackathon" target="_blank">
          GitHub repository
        </a>{" "}
        for details.
      </p>
    </div>
  );
};
