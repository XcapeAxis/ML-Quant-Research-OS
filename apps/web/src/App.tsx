import { Layout, Spin } from "antd";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "./api/client";
import type { ProjectSummary } from "./api/types";
import { Shell } from "./components/Shell";
import { ConfigPage } from "./pages/ConfigPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ResultsPage } from "./pages/ResultsPage";
import { RunDetailPage } from "./pages/RunDetailPage";
import { RunsPage } from "./pages/RunsPage";

type ProjectContextValue = {
  projects: ProjectSummary[];
  selectedProject: string | null;
  setSelectedProject: (project: string) => void;
};

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function useProjectContext(): ProjectContextValue {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error("项目上下文不可用。");
  }
  return context;
}

export function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [selectedProject, setSelectedProjectState] = useState<string | null>(() => localStorage.getItem("bt:selectedProject"));
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: api.listProjects,
    refetchInterval: 10_000,
  });

  useEffect(() => {
    if (!projectsQuery.data?.length) {
      return;
    }
    if (!selectedProject || !projectsQuery.data.some((item) => item.name === selectedProject)) {
      const next = projectsQuery.data[0].name;
      setSelectedProjectState(next);
      localStorage.setItem("bt:selectedProject", next);
    }
  }, [projectsQuery.data, selectedProject]);

  const value = useMemo<ProjectContextValue>(
    () => ({
      projects: projectsQuery.data ?? [],
      selectedProject,
      setSelectedProject: (project) => {
        setSelectedProjectState(project);
        localStorage.setItem("bt:selectedProject", project);
        if (location.pathname === "/") {
          navigate("/projects");
        }
      },
    }),
    [location.pathname, navigate, projectsQuery.data, selectedProject],
  );

  if (projectsQuery.isLoading && !projectsQuery.data) {
    return (
      <Layout className="app-shell loading-shell">
        <Spin size="large" />
      </Layout>
    );
  }

  return (
    <ProjectContext.Provider value={value}>
      <Shell>
        <Routes>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/config" element={<ConfigPage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/runs/:jobId" element={<RunDetailPage />} />
          <Route path="/results" element={<ResultsPage />} />
        </Routes>
      </Shell>
    </ProjectContext.Provider>
  );
}
