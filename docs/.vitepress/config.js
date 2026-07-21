export default {
  base: "/naso/",
  title: "NASO",
  titleTemplate: ":title - NASO Documentation",
  description: "Advanced Forensic & Intelligence Framework.",
  cleanUrls: true,
  appearance: 'dark', // Native dark mode standard
  head: [
    // Tutto first-party. 'unsafe-inline' serve perche' VitePress emette
    // uno script inline per il tema e stili inline.
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
      message: 'Released under the MIT License.' + ' · <a href="https://fabriziosalmi.github.io/privacy">Privacy &amp; legal</a>',
      copyright: 'Copyright © 2026 Fabrizio Salmi'
    }
  }
}
