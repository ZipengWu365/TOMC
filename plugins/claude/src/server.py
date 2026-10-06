"""Launch the bundled TOMC server; notebooks live outside the installation."""

from tomc.mcp_server import serve

if __name__ == "__main__":
    serve()
