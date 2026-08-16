export default {
  base: "/naso/",
  title: "NASO",
  titleTemplate: ":title - NASO Documentation",
  description: "Advanced Forensic & Intelligence Framework.",
  cleanUrls: true,
  appearance: 'dark', // Native dark mode standard
  head: [
    // Everything this site loads is first-party. 'unsafe-inline' is required
    // because VitePress emits an inline appearance script and inline styles.
    // Applied to the built site only: `vitepress dev` serves HMR over a
    // websocket, which a strict connect-src would block as soon as the dev
    // server is not same-origin (--host, or a custom server.hmr.port).
    ...(process.env.NODE_ENV === 'production'
      ? [
          [
            'meta',
            {
              'http-equiv': 'Content-Security-Policy',
              content:
                "default-src 'self'; script-src 'self' 'unsafe-inline'; " +
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; " +
                "font-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'self'",
            },
          ],
        ]
      : []),
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/naso/logo.svg' }],
    ['meta', { name: 'theme-color', content: '#000000' }]
  ],
  themeConfig: {
    logo: '/logo.svg',
    nav: [
      { text: "Overview", link: "/guide/" },
      { text: "Deploy", link: "/guide/deployment" },
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
          { text: "AI Co-Analyst", link: "/guide/ai-coanalyst" },
          { text: "MCP & GenAI", link: "/guide/mcp-integration" },
          { text: "SOAR & CTI Hooks", link: "/guide/soar-and-cti" },
          { text: "Compliance Data", link: "/guide/reporting" }
        ]
      },
      {
        text: "Running NASO",
        collapsed: false,
        items: [
          { text: "Configuration", link: "/guide/configuration" },
          { text: "Deployment", link: "/guide/deployment" },
          { text: "Security Model", link: "/guide/security" },
          { text: "Operator Runbook", link: "/guide/runbook" }
        ]
      },
      {
        text: "Project",
        collapsed: false,
        items: [
          { text: "Contributing", link: "/guide/contributing" },
          { text: "Changelog", link: "https://github.com/fabriziosalmi/naso/blob/main/CHANGELOG.md" }
        ]
      }
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/fabriziosalmi/naso' }
    ],
    footer: {
      message:
        'Released under the <a href="https://github.com/fabriziosalmi/naso/blob/main/LICENSE">AGPL-3.0 License</a>. · ' +
        '<a href="https://github.com/fabriziosalmi/naso/blob/main/LEGAL.md">Acceptable use</a> · ' +
        '<a href="https://fabriziosalmi.github.io/privacy">Privacy &amp; legal</a>',
      copyright: 'Copyright © 2026 Fabrizio Salmi'
    }
  }
}
