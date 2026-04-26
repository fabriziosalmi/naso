export default {
  base: "/naso/",
  title: "NASO",
  titleTemplate: ":title - NASO Documentation",
  description: "Advanced Forensic & Intelligence Framework.",
  cleanUrls: true,
  appearance: 'dark', // Native dark mode standard
  // Show "Last updated" footer per page based on git mtime.
  // Builds credibility: a contributor can tell at a glance whether
  // a doc is current or last touched 18 months ago.
  lastUpdated: true,
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/naso/logo.svg' }],
    ['meta', { name: 'theme-color', content: '#000000' }]
  ],
  themeConfig: {
    logo: '/logo.svg',
    nav: [
      { text: "Overview", link: "/guide/" },
      { text: "API Reference", link: "/api/" }
    ],
    search: {
      provider: 'local'
    },
    sidebar: [
      {
        text: "Platform",
        collapsed: false,
        items: [
          { text: "Getting Started", link: "/guide/" },
          { text: "Architecture", link: "/guide/architecture" },
          { text: "Configuration", link: "/guide/configuration" },
          { text: "Security", link: "/guide/security" },
          { text: "Deployment", link: "/guide/deployment" },
          { text: "Runbook", link: "/guide/runbook" }
        ]
      },
      {
        text: "Core Modules",
        collapsed: false,
        items: [
          { text: "Identity Hub", link: "/guide/identity-hub" },
          { text: "Dark Web Recon", link: "/guide/dark-recon" },
          { text: "AI Co-Analyst", link: "/guide/ai-coanalyst" },
          { text: "MCP Integration", link: "/guide/mcp-integration" },
          { text: "SOAR & CTI", link: "/guide/soar-and-cti" },
          { text: "Reporting", link: "/guide/reporting" }
        ]
      },
      {
        text: "Project",
        collapsed: false,
        items: [
          { text: "Contributing", link: "/guide/contributing" }
        ]
      }
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/fabriziosalmi/naso' }
    ],
    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright © 2026 Fabrizio Salmi'
    }
  }
}
