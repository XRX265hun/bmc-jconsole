import java.applet.Applet;
import java.applet.AppletContext;
import java.applet.AppletStub;
import java.applet.AudioClip;
import java.awt.Component;
import java.awt.Container;
import java.awt.Dimension;
import java.awt.Image;
import java.awt.Toolkit;
import java.awt.Window;
import java.awt.image.BufferedImage;
import java.awt.image.ImageProducer;
import java.awt.image.MemoryImageSource;
import java.io.InputStream;
import java.lang.reflect.Field;
import java.net.URL;
import java.security.SecureRandom;
import java.security.cert.X509Certificate;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import javax.swing.JComponent;
import javax.swing.JFrame;
import javax.swing.SwingUtilities;
import javax.swing.Timer;
import javax.swing.WindowConstants;

/**
 * Hosts the iLO 3 Java IRC applet outside a browser.
 * Video is drawn in the applet's own dispFrame using MemoryImageSource;
 * Windows DPI-aware Java 8 often leaves that surface blank/white.
 */
public final class IloAppletLauncher {
    public static void main(String[] args) throws Exception {
        System.setProperty("sun.java2d.noddraw", "true");
        System.setProperty("sun.java2d.d3d", "false");
        System.setProperty("sun.java2d.opengl", "false");
        System.setProperty("sun.java2d.dpiaware", "false");
        System.setProperty("sun.java2d.uiScale", "1");
        System.setOut(new java.io.PrintStream(System.out, true));
        if (args.length < 3) {
            System.err.println("Usage: IloAppletLauncher <mainClass> <codebaseUrl> <documentUrl> [NAME=value ...]");
            System.exit(2);
        }
        installInsecureSsl();
        String mainClass = args[0];
        URL codebase = new URL(args[1]);
        URL document = new URL(args[2]);
        Map<String, String> params = new HashMap<String, String>();
        for (int i = 3; i < args.length; i++) {
            int eq = args[i].indexOf('=');
            if (eq <= 0) {
                continue;
            }
            params.put(args[i].substring(0, eq), args[i].substring(eq + 1));
        }

        Class<?> clazz = Class.forName(mainClass);
        final Applet applet = (Applet) clazz.getDeclaredConstructor().newInstance();
        applet.setStub(new Stub(applet, codebase, document, params));

        SwingUtilities.invokeAndWait(new Runnable() {
            public void run() {
                JFrame host = new JFrame();
                host.setDefaultCloseOperation(WindowConstants.DO_NOTHING_ON_CLOSE);
                host.setUndecorated(true);
                host.setSize(1, 1);
                host.setLocation(-2000, -2000);
                host.getContentPane().add(applet);
                host.setVisible(true);
                applet.init();
            }
        });

        Thread starter = new Thread(new Runnable() {
            public void run() {
                applet.start();
            }
        }, "iLO-applet-start");
        starter.setDaemon(false);
        starter.start();

        SwingUtilities.invokeLater(new Runnable() {
            public void run() {
                Window[] windows = Window.getWindows();
                for (int i = 0; i < windows.length; i++) {
                    Window window = windows[i];
                    if (!window.isDisplayable() || window.getWidth() <= 1) {
                        continue;
                    }
                    if (window instanceof JFrame) {
                        ((JFrame) window).setDefaultCloseOperation(WindowConstants.EXIT_ON_CLOSE);
                    }
                    window.setVisible(true);
                    window.toFront();
                }
            }
        });

        SwingUtilities.invokeLater(new Runnable() {
            public void run() {
                Timer timer = new Timer(800, null);
                timer.setRepeats(true);
                final int[] ticks = new int[] { 0 };
                timer.addActionListener(new java.awt.event.ActionListener() {
                    public void actionPerformed(java.awt.event.ActionEvent e) {
                        ticks[0]++;
                        boolean ready = fixVideoSurface(applet);
                        System.out.flush();
                        if (ready || ticks[0] >= 40) {
                            ((Timer) e.getSource()).stop();
                        }
                    }
                });
                timer.start();
            }
        });
    }

    private static boolean fixVideoSurface(Applet applet) {
        try {
            Field dispField = applet.getClass().getField("dispFrame");
            Object disp = dispField.get(applet);
            JComponent screen = findDvcwin(applet);
            boolean videoReady = false;
            if (screen != null) {
                Field sx = screen.getClass().getDeclaredField("screen_x");
                Field sy = screen.getClass().getDeclaredField("screen_y");
                Field firstImageField = screen.getClass().getDeclaredField("first_image");
                Field imageSourceField = screen.getClass().getDeclaredField("image_source");
                Field clearScreenField = screen.getClass().getDeclaredField("clear_screen");
                Field pixelsField = screen.getClass().getDeclaredField("pixel_buffer");
                sx.setAccessible(true);
                sy.setAccessible(true);
                firstImageField.setAccessible(true);
                imageSourceField.setAccessible(true);
                clearScreenField.setAccessible(true);
                pixelsField.setAccessible(true);
                int w = sx.getInt(screen);
                int h = sy.getInt(screen);
                Image firstImage = (Image) firstImageField.get(screen);
                int imageW = firstImage == null ? -1 : firstImage.getWidth(null);
                int imageH = firstImage == null ? -1 : firstImage.getHeight(null);
                int[] pixels = (int[]) pixelsField.get(screen);
                int sample = 0;
                if (pixels != null && pixels.length > 10000) {
                    sample = pixels[10000];
                }
                System.out.println("dvcwin screen_x=" + w + " screen_y=" + h
                    + " size=" + screen.getWidth() + "x" + screen.getHeight()
                    + " showing=" + screen.isShowing()
                    + " displayable=" + screen.isDisplayable()
                    + " first_image=" + (firstImage == null ? "null" : imageW + "x" + imageH)
                    + " pixel_sample=" + Integer.toHexString(sample));
                System.out.flush();
                if (w <= 1 || h <= 1) {
                    try {
                        Object remcons = applet.getClass().getField("remconsObj").get(applet);
                        Object session = remcons.getClass().getField("session").get(remcons);
                        Field cx = session.getClass().getDeclaredField("screen_x");
                        Field cy = session.getClass().getDeclaredField("screen_y");
                        cx.setAccessible(true);
                        cy.setAccessible(true);
                        int cw = cx.getInt(session);
                        int ch = cy.getInt(session);
                        System.out.println("cim screen_x=" + cw + " screen_y=" + ch);
                        if (cw > 1 && ch > 1) {
                            screen.getClass().getMethod("set_abs_dimensions", int.class, int.class)
                                .invoke(screen, Integer.valueOf(cw), Integer.valueOf(ch));
                            w = cw;
                            h = ch;
                            firstImage = (Image) firstImageField.get(screen);
                        }
                    } catch (Exception inner) {
                        System.out.println("cim size lookup: " + inner);
                    }
                }
                boolean imageMissing = firstImage == null || imageW <= 1 || imageH <= 1;
                if (w > 1 && h > 1 && screen.isDisplayable() && imageMissing) {
                    System.out.println("recreating first_image after displayable");
                    clearScreenField.setBoolean(screen, true);
                    screen.getClass().getMethod("set_abs_dimensions", int.class, int.class)
                        .invoke(screen, Integer.valueOf(w), Integer.valueOf(h));
                    firstImage = (Image) firstImageField.get(screen);
                    if (firstImage == null) {
                        Object source = imageSourceField.get(screen);
                        if (source instanceof ImageProducer) {
                            firstImage = screen.createImage((ImageProducer) source);
                            if (firstImage == null) {
                                firstImage = Toolkit.getDefaultToolkit().createImage((ImageProducer) source);
                            }
                            firstImageField.set(screen, firstImage);
                        }
                    }
                    Object source = imageSourceField.get(screen);
                    if (source instanceof MemoryImageSource) {
                        ((MemoryImageSource) source).newPixels();
                    }
                    imageW = firstImage == null ? -1 : firstImage.getWidth(null);
                    System.out.println("first_image after recreate="
                        + (firstImage == null ? "null" : imageW + "x" + firstImage.getHeight(null)));
                }
                if (w > 1 && h > 1) {
                    screen.setPreferredSize(new Dimension(w, h));
                    screen.setMinimumSize(new Dimension(w, h));
                    screen.setSize(w, h);
                    Container parent = screen.getParent();
                    while (parent != null) {
                        parent.invalidate();
                        parent = parent.getParent();
                    }
                    screen.revalidate();
                    screen.repaint();
                }
                videoReady = screen.isShowing() && firstImage != null && imageW > 1 && sample != 0;
            }
            if (disp instanceof Window) {
                Window window = (Window) disp;
                window.invalidate();
                window.validate();
                window.repaint();
                if (window instanceof JFrame) {
                    ((JFrame) window).toFront();
                }
            }
            return videoReady;
        } catch (Exception ex) {
            System.out.println("fixVideoSurface: " + ex);
            return false;
        }
    }

    private static JComponent findDvcwin(Applet applet) throws Exception {
        Object remcons = applet.getClass().getField("remconsObj").get(applet);
        Object session = remcons.getClass().getField("session").get(remcons);
        Class<?> telnet = Class.forName("com.hp.ilo2.remcons.telnet");
        Field screenField = telnet.getDeclaredField("screen");
        screenField.setAccessible(true);
        Object screen = screenField.get(session);
        return (screen instanceof JComponent) ? (JComponent) screen : null;
    }

    private static void installInsecureSsl() throws Exception {
        TrustManager[] trustAll = new TrustManager[] {
            new X509TrustManager() {
                public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
                public void checkClientTrusted(X509Certificate[] chain, String authType) { }
                public void checkServerTrusted(X509Certificate[] chain, String authType) { }
            }
        };
        SSLContext context = SSLContext.getInstance("TLS");
        context.init(null, trustAll, new SecureRandom());
        SSLContext.setDefault(context);
        HttpsURLConnection.setDefaultSSLSocketFactory(context.getSocketFactory());
        HttpsURLConnection.setDefaultHostnameVerifier(new javax.net.ssl.HostnameVerifier() {
            public boolean verify(String hostname, javax.net.ssl.SSLSession session) {
                return true;
            }
        });
    }

    private static final class Stub implements AppletStub, AppletContext {
        private final Applet applet;
        private final URL codebase;
        private final URL document;
        private final Map<String, String> params;

        Stub(Applet applet, URL codebase, URL document, Map<String, String> params) {
            this.applet = applet;
            this.codebase = codebase;
            this.document = document;
            this.params = params;
        }

        public boolean isActive() { return true; }
        public URL getDocumentBase() { return document; }
        public URL getCodeBase() { return codebase; }
        public String getParameter(String name) { return params.get(name); }
        public AppletContext getAppletContext() { return this; }
        public void appletResize(int width, int height) { }

        public AudioClip getAudioClip(URL url) { return null; }
        public Image getImage(URL url) {
            if (url == null) {
                return new BufferedImage(16, 16, BufferedImage.TYPE_INT_ARGB);
            }
            try {
                return Toolkit.getDefaultToolkit().getImage(url);
            } catch (Exception ex) {
                return new BufferedImage(16, 16, BufferedImage.TYPE_INT_ARGB);
            }
        }
        public Applet getApplet(String name) { return applet; }
        public Enumeration<Applet> getApplets() {
            return new Enumeration<Applet>() {
                private boolean once = true;
                public boolean hasMoreElements() { return once; }
                public Applet nextElement() { once = false; return applet; }
            };
        }
        public void showDocument(URL url) { System.out.println("showDocument " + url); }
        public void showDocument(URL url, String target) { showDocument(url); }
        public void showStatus(String status) { System.out.println(status); }
        public void setStream(String key, InputStream stream) { }
        public InputStream getStream(String key) { return null; }
        public Iterator<String> getStreamKeys() { return params.keySet().iterator(); }
    }
}
