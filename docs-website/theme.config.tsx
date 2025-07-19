import React from "react";
import { DocsThemeConfig } from "nextra-theme-docs";

const config: DocsThemeConfig = {
  logo: <span style={{ fontWeight: 800, fontSize: "1.5rem" }}>📁 Dossier</span>,
  project: {
    link: "https://github.com/ssenthilnathan3/dossier",
  },
  chat: {
    link: "https://github.com/ssenthilnathan3/dossier",
  },
  docsRepositoryBase:
    "https://github.com/ssenthilnathan3/dossier/tree/main/docs-website",
  footer: {
    text: (
      <span>
        MIT {new Date().getFullYear()} ©{" "}
        <a href="https://github.com/ssenthilnathan3/dossier" target="_blank">
          Dossier RAG System
        </a>
        .
      </span>
    ),
  },
  head: (
    <>
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <meta
        property="og:title"
        content="Dossier - Live RAG System Documentation"
      />
      <meta
        property="og:description"
        content="Complete documentation for the Dossier Live RAG System for Frappe documents"
      />
      <meta property="og:type" content="website" />
      <meta
        name="description"
        content="Complete documentation for the Dossier Live RAG System for Frappe documents"
      />
      <meta
        name="keywords"
        content="dossier, rag, frappe, documentation, ai, vector search, llm, microservices"
      />
      <link rel="icon" type="image/x-icon" href="/favicon.ico" />
      <link rel="preconnect" href="https://fonts.googleapis.com" />
    </>
  ),
  sidebar: {
    titleComponent({ title, type }) {
      if (type === "separator") {
        return <span className="cursor-default">{title}</span>;
      }
      return <>{title}</>;
    },
    defaultMenuCollapseLevel: 1,
    toggleButton: true,
  },
  toc: {
    backToTop: true,
  },
  editLink: {
    text: "Edit this page on GitHub →",
  },
  feedback: {
    content: "Question? Give us feedback →",
    labels: "feedback",
  },
  search: {
    placeholder: "Search documentation...",
  },
  useNextSeoProps() {
    return {
      titleTemplate: "%s – Dossier RAG System",
    };
  },
  primaryHue: {
    dark: 200,
    light: 220,
  },
  darkMode: true,

  nextThemes: {
    defaultTheme: "dark",
  },
};

export default config;
