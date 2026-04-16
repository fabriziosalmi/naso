export default {
  base: "/naso/",
  title: "NASO Documentation",
  description: "Advanced Forensic & Intelligence Framework",
  themeConfig: {
    nav: [
      { text: "Home", link: "/" },
      { text: "Guide", link: "/guide/" },
      { text: "API", link: "/api/" }
    ],
    sidebar: [
      {
        text: "Introduction",
        items: [
          { text: "What is NASO?", link: "/guide/" },
          { text: "Architecture", link: "/guide/architecture" }
        ]
      },
      {
        text: "Modules",
        items: [
          { text: "Identity Hub", link: "/guide/identity-hub" },
          { text: "Dark Web Recon", link: "/guide/dark-recon" },
          { text: "Reporting", link: "/guide/reporting" }
        ]
      }
    ]
  }
}
