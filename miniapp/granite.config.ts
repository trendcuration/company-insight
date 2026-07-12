import { defineConfig } from '@apps-in-toss/web-framework/config';

export default defineConfig({
  appName: 'company-insight',
  brand: {
    displayName: '기업인사이트',
    primaryColor: '#3498DB',
    icon: 'https://static.toss.im/appsintoss/21275/ea0d96fc-638a-448f-ab14-137cd86f5bcf.png',
  },
  permissions: [],
  web: {
    host: 'localhost',
    port: 5173,
    commands: {
      dev: 'vite',
      build: 'vite build',
    },
  },
  webViewProps: {
    type: 'partner',
  },
  outdir: 'dist',
});
