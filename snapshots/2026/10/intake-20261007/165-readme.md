# Foxglove MCAP Explorer

Inspect MCAP files and visualize with [Foxglove](https://foxglove.dev/) in VS Code.

![Embedded Foxglove viewer plotting telemetry from an MCAP recording](assets/screenshot.png)

## Get started

1. Install [**Foxglove MCAP Explorer** from the Visual Studio Marketplace](https://marketplace.visualstudio.com/items?itemName=Foxglove.foxglove-mcap-explorer).
2. Open an `.mcap` file to see file size, duration, message counts, channels, and schemas. No CLI or account is needed for file information.
3. Select **Foxglove** to visualize the recording. Sign in if prompted. Visualization requires internet access and [Foxglove Embed access](https://docs.foxglove.dev/docs/embed).

If the file opens in another editor, choose **Reopen Editor With… → Foxglove MCAP Explorer**.

## Layouts and sign-in

Under **Viewer options**:

- **Load shared layouts…** loads organization layouts using a Foxglove API key with layout read access.
- **Import JSON…** loads an exported layout, including personal layouts.
- **Sign-in help → Open sign-in page** lets you enter the viewer’s activation code if its sign-in popup is blocked.

Layout edits are saved locally, not back to your Foxglove account. API keys are stored securely by the editor; use **MCAP: Clear Foxglove API Key** in the Command Palette to remove one.

## Stay in touch

Join our [Discord](https://foxglove.dev/chat) to ask questions, share feedback, and stay up to date on what our team is working on.
