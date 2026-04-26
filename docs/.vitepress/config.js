export default {
  base: "/naso/",
  title: "NASO",
  titleTemplate: ":title - NASO Documentation",
  description: "Advanced Forensic & Intelligence Framework.",
  cleanUrls: true,
  appearance: 'dark', // Native dark mode standard
  // docs/internal/* holds historical scratch notes (planning docs, old
  // walkthroughs). Not part of the public site; explicitly excluded so a
  // stray <a href> never resolves to one.
  srcExclude: ['internal/**'],
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
          { text: "Introduction", link: "/guide/" },
          { text: "Architecture", link: "/guide/architecture" }
        ]
      },
      {
        text: "Core Modules",
        collapsed: false,
        items: [
          { text: "Identity Hub", link: "/guide/identity-hub" },
          { text: "Dark Web Recon", link: "/guide/dark-recon" },
          { text: "MCP & GenAI", link: "/guide/mcp-integration" },
          { text: "SOAR & CTI Hooks", link: "/guide/soar-and-cti" },
          { text: "Compliance Data", link: "/guide/reporting" }
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
