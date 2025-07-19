# Dossier Documentation Website

A modern, GitBook-style documentation website for the Dossier Live RAG System, built with [Nextra](https://nextra.site/) and Next.js.

## 🚀 Quick Start

### Prerequisites

- Node.js 18+
- npm or yarn package manager

### Development Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Open http://localhost:3000
```

### Production Build

```bash
# Build for production
npm run build

# Start production server
npm start

# Or build static site for deployment
npm run export
```

## 📁 Project Structure

```
docs-website/
├── pages/                 # Documentation pages (MDX format)
│   ├── index.mdx         # Homepage
│   ├── getting-started/  # Getting started guide
│   ├── architecture/     # System architecture docs
│   ├── features/         # Feature documentation
│   ├── deployment/       # Deployment guides
│   ├── api-reference/    # API documentation
│   ├── troubleshooting/  # Troubleshooting guides
│   └── _meta.json        # Navigation configuration
├── theme.config.tsx      # Nextra theme configuration
├── next.config.js        # Next.js configuration
└── package.json          # Dependencies and scripts
```

## 🎨 Customization

### Theme Configuration

Edit `theme.config.tsx` to customize:

- Site logo and branding
- Navigation structure
- Footer content
- Social links
- Search functionality
- Color scheme

### Adding New Pages

1. Create new MDX files in the `pages/` directory
2. Update `_meta.json` files for navigation
3. Use frontmatter for page metadata:

```mdx
---
title: Page Title
description: Page description for SEO
---

# Page Content

Your markdown content here...
```

### Navigation Structure

Update `pages/_meta.json` to modify main navigation:

```json
{
  "index": "Introduction",
  "getting-started": "🚀 Getting Started",
  "architecture": "🏗️ Architecture",
  "features": "✨ Features"
}
```

## 🚀 Deployment

### Vercel (Recommended)

1. Connect your GitHub repository to Vercel
2. Vercel will automatically detect Next.js and deploy
3. Set build command: `npm run build`
4. Set output directory: `out` (for static export)

### Netlify

1. Connect your GitHub repository to Netlify
2. Set build command: `npm run build && npm run export`
3. Set publish directory: `out`

### Static Hosting

```bash
# Build static site
npm run export

# Deploy the 'out' directory to any static host
# (GitHub Pages, AWS S3, Azure Storage, etc.)
```

### Docker Deployment

```dockerfile
FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
```

## 📝 Content Guidelines

### Writing Style

- Use clear, concise language
- Include code examples where relevant
- Add callouts for important information
- Use proper headings hierarchy (H1 → H2 → H3)

### Code Examples

Use language-specific syntax highlighting:

```bash
# Bash commands
make quick-start
```

```python
# Python code
from dossier import Client
client = Client()
```

```javascript
// JavaScript code
const client = new DossierClient();
```

### Callouts and Admonitions

```mdx
import { Callout } from 'nextra/components'

<Callout type="info">
  This is an info callout
</Callout>

<Callout type="warning">
  This is a warning callout
</Callout>

<Callout type="error">
  This is an error callout
</Callout>
```

### Interactive Components

```mdx
import { Cards, Card } from 'nextra/components'

<Cards>
  <Card title="Card Title" href="/link">
    Card description
  </Card>
</Cards>
```

## 🔧 Development

### Local Development

```bash
# Install dependencies
npm install

# Start dev server with hot reload
npm run dev

# Build and test production locally
npm run build
npm start
```

### Adding Features

1. **New Documentation Section**: Create folder in `pages/` with `index.mdx` and `_meta.json`
2. **Interactive Components**: Add to `components/` directory
3. **Custom Styling**: Modify theme configuration or add CSS modules
4. **Search Integration**: Configure in `theme.config.tsx`

### Content Updates

1. Edit MDX files in `pages/`
2. Test locally with `npm run dev`
3. Commit and push changes
4. Deployment happens automatically

## 📊 Analytics and SEO

### Google Analytics

Add to `theme.config.tsx`:

```typescript
export default {
  head: (
    <>
      {/* Google Analytics */}
      <script
        async
        src="https://www.googletagmanager.com/gtag/js?id=GA_MEASUREMENT_ID"
      />
      <script
        dangerouslySetInnerHTML={{
          __html: `
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'GA_MEASUREMENT_ID');
          `,
        }}
      />
    </>
  )
}
```

### SEO Optimization

- Use descriptive page titles and descriptions
- Add Open Graph meta tags
- Include keywords in content naturally
- Optimize images and use alt text
- Ensure fast loading times

## 🤝 Contributing

### Content Contributions

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally
5. Submit a pull request

### Reporting Issues

- Use GitHub Issues for bug reports
- Include steps to reproduce
- Provide browser/environment details
- Suggest improvements

## 📄 License

This documentation website is part of the Dossier project and is licensed under the MIT License.

## 🆘 Support

- **Documentation Issues**: [GitHub Issues](https://github.com/your-org/dossier/issues)
- **General Questions**: [GitHub Discussions](https://github.com/your-org/dossier/discussions)
- **Website Problems**: Check browser console and report issues

---

Built with ❤️ using [Nextra](https://nextra.site/) and [Next.js](https://nextjs.org/)trigge
