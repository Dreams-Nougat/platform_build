/*
 * Copyright (C) 2008 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.android.signapk;

import org.bouncycastle.asn1.ASN1InputStream;
import org.bouncycastle.asn1.ASN1ObjectIdentifier;
import org.bouncycastle.asn1.DEROutputStream;
import org.bouncycastle.asn1.cms.CMSObjectIdentifiers;
import org.bouncycastle.cert.jcajce.JcaCertStore;
import org.bouncycastle.cms.CMSException;
import org.bouncycastle.cms.CMSProcessableByteArray;
import org.bouncycastle.cms.CMSSignedData;
import org.bouncycastle.cms.CMSSignedDataGenerator;
import org.bouncycastle.cms.CMSTypedData;
import org.bouncycastle.cms.jcajce.JcaSignerInfoGeneratorBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.OperatorCreationException;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.operator.jcajce.JcaDigestCalculatorProviderBuilder;
import org.bouncycastle.util.encoders.Base64;

import java.io.BufferedReader;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.FilterOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.PrintStream;
import java.security.DigestOutputStream;
import java.security.GeneralSecurityException;
import java.security.Key;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.PrivateKey;
import java.security.Provider;
import java.security.Security;
import java.security.cert.CertificateEncodingException;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.security.spec.InvalidKeySpecException;
import java.security.spec.KeySpec;
import java.security.spec.PKCS8EncodedKeySpec;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.Map;
import java.util.TreeMap;
import java.util.jar.Attributes;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;
import java.util.jar.JarOutputStream;
import java.util.jar.Manifest;
import java.util.regex.Pattern;
import javax.crypto.Cipher;
import javax.crypto.EncryptedPrivateKeyInfo;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;

/**
 * Command line tool to sign JAR files (including APKs and OTA updates) in
 * a way compatible with the mincrypt verifier, using SHA1 and RSA keys.
 */
class SignApk {
    /** SDK level corresponding to Jelly Bean MR2. */
    private static final int JELLY_BEAN_MR2 = 18;
    private static final String[] MESSAGE_DIGEST_NAMES = new String[] { "SHA1", "SHA-256" };
    private static final String CERT_SF_NAME = "META-INF/CERT.SF";
    private static final String CERT_SIG_NAME = "META-INF/CERT.%s";
    private static final String CERT_SF_MULTI_NAME = "META-INF/CERT%d.SF";
    private static final String CERT_SIG_MULTI_NAME = "META-INF/CERT%d.%s";

    private static final String OTACERT_NAME = "META-INF/com/android/otacert";

    private static final MessageDigest[] sMessageDigests =
            new MessageDigest[MESSAGE_DIGEST_NAMES.length];
    static {
        for (int i = 0; i < sMessageDigests.length; i++) {
            try {
                sMessageDigests[i] = MessageDigest.getInstance(MESSAGE_DIGEST_NAMES[i]);
            } catch (NoSuchAlgorithmException e) {
                throw new RuntimeException(MESSAGE_DIGEST_NAMES[i] + " must be supported", e);
            }
        }
    }

    private static Provider sBouncyCastleProvider;

    // Files matching this pattern are not copied to the output.
    private static Pattern stripPattern =
        Pattern.compile("^(META-INF/((.*)[.](SF|RSA|DSA|EC)|com/android/otacert))|(" +
                        Pattern.quote(JarFile.MANIFEST_NAME) + ")$");

    /** Used as a hint about what can be supported. */
    private static int sMinSdkVersion = 1;

    private static X509Certificate readPublicKey(File file)
        throws IOException, GeneralSecurityException {
        FileInputStream input = new FileInputStream(file);
        try {
            CertificateFactory cf = CertificateFactory.getInstance("X.509");
            return (X509Certificate) cf.generateCertificate(input);
        } finally {
            input.close();
        }
    }

    /**
     * Reads the password from stdin and returns it as a string.
     *
     * @param keyFile The file containing the private key.  Used to prompt the user.
     */
    private static String readPassword(File keyFile) {
        // TODO: use Console.readPassword() when it's available.
        System.out.print("Enter password for " + keyFile + " (password will not be hidden): ");
        System.out.flush();
        BufferedReader stdin = new BufferedReader(new InputStreamReader(System.in));
        try {
            return stdin.readLine();
        } catch (IOException ex) {
            return null;
        }
    }

    /**
     * Decrypt an encrypted PKCS 8 format private key.
     *
     * Based on ghstark's post on Aug 6, 2006 at
     * http://forums.sun.com/thread.jspa?threadID=758133&messageID=4330949
     *
     * @param encryptedPrivateKey The raw data of the private key
     * @param keyFile The file containing the private key
     */
    private static KeySpec decryptPrivateKey(byte[] encryptedPrivateKey, File keyFile)
        throws GeneralSecurityException {
        EncryptedPrivateKeyInfo epkInfo;
        try {
            epkInfo = new EncryptedPrivateKeyInfo(encryptedPrivateKey);
        } catch (IOException ex) {
            // Probably not an encrypted key.
            return null;
        }

        char[] password = readPassword(keyFile).toCharArray();

        SecretKeyFactory skFactory = SecretKeyFactory.getInstance(epkInfo.getAlgName());
        Key key = skFactory.generateSecret(new PBEKeySpec(password));

        Cipher cipher = Cipher.getInstance(epkInfo.getAlgName());
        cipher.init(Cipher.DECRYPT_MODE, key, epkInfo.getAlgParameters());

        try {
            return epkInfo.getKeySpec(cipher);
        } catch (InvalidKeySpecException ex) {
            System.err.println("signapk: Password for " + keyFile + " may be bad.");
            throw ex;
        }
    }

    /** Read a PKCS#8 format private key. */
    private static PrivateKey readPrivateKey(File file)
        throws IOException, GeneralSecurityException {
        DataInputStream input = new DataInputStream(new FileInputStream(file));
        try {
            byte[] bytes = new byte[(int) file.length()];
            input.read(bytes);

            KeySpec spec = decryptPrivateKey(bytes, file);
            if (spec == null) {
                spec = new PKCS8EncodedKeySpec(bytes);
            }

            PrivateKey key;
            key = decodeAsKeyType(spec, "RSA");
            if (key != null) {
                return key;
            }

            key = decodeAsKeyType(spec, "DSA");
            if (key != null) {
                return key;
            }

            if (sMinSdkVersion < JELLY_BEAN_MR2) {
                throw new NoSuchAlgorithmException("Must specify an RSA or DSA key when -minsdk " +
                        sMinSdkVersion);
            }

            key = decodeAsKeyType(spec, "EC");
            if (key != null) {
                return key;
            }

            throw new NoSuchAlgorithmException("Must be an RSA, DSA, or EC key");
        } finally {
            input.close();
        }
    }

    private static PrivateKey decodeAsKeyType(KeySpec spec, String keyType)
            throws GeneralSecurityException {
        try {
            return KeyFactory.getInstance(keyType).generatePrivate(spec);
        } catch (InvalidKeySpecException e) {
            return null;
        }
    }

    /** Add the digest of every file to the manifest, creating it if necessary. */
    private static Manifest addDigestsToManifest(JarFile jar)
        throws IOException, GeneralSecurityException {
        Manifest input = jar.getManifest();
        Manifest output = new Manifest();
        Attributes main = output.getMainAttributes();
        if (input != null) {
            main.putAll(input.getMainAttributes());
        } else {
            main.putValue("Manifest-Version", "1.0");
            main.putValue("Created-By", "1.0 (Android SignApk)");
        }

        byte[] buffer = new byte[4096];

        // We sort the input entries by name, and add them to the
        // output manifest in sorted order.  We expect that the output
        // map will be deterministic.

        TreeMap<String, JarEntry> byName = new TreeMap<String, JarEntry>();

        for (Enumeration<JarEntry> e = jar.entries(); e.hasMoreElements(); ) {
            JarEntry entry = e.nextElement();
            byName.put(entry.getName(), entry);
        }

        for (JarEntry entry: byName.values()) {
            String name = entry.getName();
            if (!entry.isDirectory() &&
                    (stripPattern == null || !stripPattern.matcher(name).matches())) {
                Attributes attr = null;
                if (input != null) attr = input.getAttributes(name);
                attr = attr != null ? new Attributes(attr) : new Attributes();
                addDigestsForEntry(attr, jar.getInputStream(entry), buffer);
                output.getEntries().put(name, attr);
            }
        }

        return output;
    }

    /**
     * Computes a Base64-encoded hash of {@code data} for all the supported
     * digests.
     */
    private static void addDigestsForEntry(Attributes attr, InputStream data, byte[] buffer)
            throws IOException {
        for (int i = 0; i < sMessageDigests.length; i++) {
            sMessageDigests[i].reset();
        }
        int num;
        while ((num = data.read(buffer)) > 0) {
            for (int i = 0; i < sMessageDigests.length; i++) {
                sMessageDigests[i].update(buffer, 0, num);
            }
        }
        for (int i = 0; i < sMessageDigests.length; i++) {
            attr.putValue(MESSAGE_DIGEST_NAMES[i] + "-Digest",
                    new String(Base64.encode(sMessageDigests[i].digest()), "ASCII"));
        }
    }

    /**
     * Computes a Base64-encoded hash of {@code data} for all the supported
     * digests.
     */
    private static void addDigestsForEntry(Attributes attr, MessageDigest[] messageDigests,
            String suffix) throws IOException {
        for (int i = 0; i < MESSAGE_DIGEST_NAMES.length; i++) {
            final MessageDigest md = messageDigests[i];
            attr.putValue(MESSAGE_DIGEST_NAMES[i] + suffix,
                    new String(Base64.encode(md.digest()), "ASCII"));
        }
    }

    /** Clear all message digests. */
    private static MessageDigest[] resetDigests() {
        for (MessageDigest md : sMessageDigests) {
            md.reset();
        }
        return sMessageDigests;
    }

    /**
     * Add a copy of the public key to the archive; this should
     * exactly match one of the files in
     * /system/etc/security/otacerts.zip on the device.  (The same
     * cert can be extracted from the CERT.RSA file but this is much
     * easier to get at.)
     */
    private static void addOtacert(JarOutputStream outputJar,
                                   File publicKeyFile,
                                   long timestamp,
                                   Manifest manifest)
        throws IOException, GeneralSecurityException {

        JarEntry je = new JarEntry(OTACERT_NAME);
        je.setTime(timestamp);
        outputJar.putNextEntry(je);

        MultiDigestOutputStream mdStream = new MultiDigestOutputStream(outputJar, resetDigests());
        FileInputStream input = new FileInputStream(publicKeyFile);
        byte[] b = new byte[4096];
        int read;
        while ((read = input.read(b)) != -1) {
            mdStream.write(b, 0, read);
        }
        input.close();

        Attributes attr = new Attributes();
        addDigestsForEntry(attr, mdStream.getMessageDigests(), "-Digest");
        manifest.getEntries().put(OTACERT_NAME, attr);
    }

    private static class MultiDigestOutputStream extends FilterOutputStream {
        private MessageDigest[] mds;

        public MultiDigestOutputStream(OutputStream out, MessageDigest[] mds) {
            super(out);
            this.mds = mds;
        }

        @Override
        public void write(byte[] buffer, int offset, int length) throws IOException {
            super.write(buffer, offset, length);

            for (MessageDigest md : mds) {
                md.update(buffer, offset, length);
            }
        }

        @Override
        public void write(int oneByte) throws IOException {
            super.write(oneByte);

            for (MessageDigest md : mds) {
                md.update((byte) oneByte);
            }
        }

        public MessageDigest[] getMessageDigests() {
            return mds;
        }
    }

    /** Write to another stream and track how many bytes have been
     *  written.
     */
    private static class CountOutputStream extends FilterOutputStream {
        private int mCount;

        public CountOutputStream(OutputStream out) {
            super(out);
            mCount = 0;
        }

        @Override
        public void write(int b) throws IOException {
            super.write(b);
            mCount++;
        }

        @Override
        public void write(byte[] b, int off, int len) throws IOException {
            super.write(b, off, len);
            mCount += len;
        }

        public int size() {
            return mCount;
        }
    }

    /** Write a .SF file with a digest of the specified manifest. */
    private static void writeSignatureFile(Manifest manifest, OutputStream out)
        throws IOException, GeneralSecurityException {
        Manifest sf = new Manifest();
        Attributes main = sf.getMainAttributes();
        main.putValue("Signature-Version", "1.0");
        main.putValue("Created-By", "1.0 (Android SignApk)");

        MultiDigestOutputStream mdStream = new MultiDigestOutputStream(
                new ByteArrayOutputStream(), resetDigests());
        PrintStream print = new PrintStream(mdStream, true, "UTF-8");

        // Digest of the entire manifest
        manifest.write(print);
        print.flush();
        addDigestsForEntry(main, mdStream.getMessageDigests(), "-Digest-Manifest");

        Map<String, Attributes> entries = manifest.getEntries();
        for (Map.Entry<String, Attributes> entry : entries.entrySet()) {
            // Digest of the manifest stanza for this entry.
            print.print("Name: " + entry.getKey() + "\r\n");
            for (Map.Entry<Object, Object> att : entry.getValue().entrySet()) {
                print.print(att.getKey() + ": " + att.getValue() + "\r\n");
            }
            print.print("\r\n");
            print.flush();

            Attributes sfAttr = new Attributes();
            addDigestsForEntry(sfAttr, mdStream.getMessageDigests(), "-Digest");
            sf.getEntries().put(entry.getKey(), sfAttr);
        }

        CountOutputStream cout = new CountOutputStream(out);
        sf.write(cout);

        // A bug in the java.util.jar implementation of Android platforms
        // up to version 1.6 will cause a spurious IOException to be thrown
        // if the length of the signature file is a multiple of 1024 bytes.
        // As a workaround, add an extra CRLF in this case.
        if ((cout.size() % 1024) == 0) {
            cout.write('\r');
            cout.write('\n');
        }
    }

    /** Sign data and write the digital signature to 'out'. */
    private static void writeSignatureBlock(
        CMSTypedData data, X509Certificate publicKey, PrivateKey privateKey,
        OutputStream out)
        throws IOException,
               CertificateEncodingException,
               OperatorCreationException,
               CMSException {
        ArrayList<X509Certificate> certList = new ArrayList<X509Certificate>(1);
        certList.add(publicKey);
        JcaCertStore certs = new JcaCertStore(certList);

        CMSSignedDataGenerator gen = new CMSSignedDataGenerator();
        ContentSigner sha1Signer = new JcaContentSignerBuilder(getSigAlgoForKeyType(privateKey))
            .setProvider(sBouncyCastleProvider)
            .build(privateKey);
        gen.addSignerInfoGenerator(
            new JcaSignerInfoGeneratorBuilder(
                new JcaDigestCalculatorProviderBuilder()
                .setProvider(sBouncyCastleProvider)
                .build())
            .setDirectSignature(true)
            .build(sha1Signer, publicKey));
        gen.addCertificates(certs);
        CMSSignedData sigData = gen.generate(data, false);

        ASN1InputStream asn1 = new ASN1InputStream(sigData.getEncoded());
        DEROutputStream dos = new DEROutputStream(out);
        dos.writeObject(asn1.readObject());
    }

    /** Returns the expected signature algorithm for this key type. */
    private static String getSigAlgoForKeyType(PrivateKey privateKey) {
        if ("RSA".equalsIgnoreCase(privateKey.getAlgorithm())) {
            if (sMinSdkVersion < JELLY_BEAN_MR2) {
                return "SHA1withRSA";
            } else {
                return "SHA256withRSA";
            }
        } else if ("DSA".equalsIgnoreCase(privateKey.getAlgorithm())) {
            return "SHA256withDSA";
        } else if ("EC".equalsIgnoreCase(privateKey.getAlgorithm())) {
            return "SHA256withECDSA";
        } else {
            throw new RuntimeException("Unknown key type supplied: " + privateKey.getAlgorithm());
        }
    }

    /**
     * Copy all the files in a manifest from input to output.  We set
     * the modification times in the output to a fixed time, so as to
     * reduce variation in the output file and make incremental OTAs
     * more efficient.
     */
    private static void copyFiles(Manifest manifest,
                                  JarFile in, JarOutputStream out, long timestamp) throws IOException {
        byte[] buffer = new byte[4096];
        int num;

        Map<String, Attributes> entries = manifest.getEntries();
        ArrayList<String> names = new ArrayList<String>(entries.keySet());
        Collections.sort(names);
        for (String name : names) {
            JarEntry inEntry = in.getJarEntry(name);
            JarEntry outEntry = null;
            if (inEntry.getMethod() == JarEntry.STORED) {
                // Preserve the STORED method of the input entry.
                outEntry = new JarEntry(inEntry);
            } else {
                // Create a new entry so that the compressed len is recomputed.
                outEntry = new JarEntry(name);
            }
            outEntry.setTime(timestamp);
            out.putNextEntry(outEntry);

            InputStream data = in.getInputStream(inEntry);
            while ((num = data.read(buffer)) > 0) {
                out.write(buffer, 0, num);
            }
            out.flush();
        }
    }

    private static class WholeFileSignerOutputStream extends FilterOutputStream {
        private boolean closing = false;
        private ByteArrayOutputStream footer = new ByteArrayOutputStream();
        private OutputStream tee;

        public WholeFileSignerOutputStream(OutputStream out, OutputStream tee) {
            super(out);
            this.tee = tee;
        }

        public void notifyClosing() {
            closing = true;
        }

        public void finish() throws IOException {
            closing = false;

            byte[] data = footer.toByteArray();
            if (data.length < 2)
                throw new IOException("Less than two bytes written to footer");
            write(data, 0, data.length - 2);
        }

        public byte[] getTail() {
            return footer.toByteArray();
        }

        @Override
        public void write(byte[] b) throws IOException {
            write(b, 0, b.length);
        }

        @Override
        public void write(byte[] b, int off, int len) throws IOException {
            if (closing) {
                // if the jar is about to close, save the footer that will be written
                footer.write(b, off, len);
            }
            else {
                // write to both output streams. out is the CMSTypedData signer and tee is the file.
                out.write(b, off, len);
                tee.write(b, off, len);
            }
        }

        @Override
        public void write(int b) throws IOException {
            if (closing) {
                // if the jar is about to close, save the footer that will be written
                footer.write(b);
            }
            else {
                // write to both output streams. out is the CMSTypedData signer and tee is the file.
                out.write(b);
                tee.write(b);
            }
        }
    }

    private static class CMSSigner implements CMSTypedData {
        private JarFile inputJar;
        private File publicKeyFile;
        private X509Certificate publicKey;
        private PrivateKey privateKey;
        private String outputFile;
        private OutputStream outputStream;
        private final ASN1ObjectIdentifier type;
        private WholeFileSignerOutputStream signer;

        public CMSSigner(JarFile inputJar, File publicKeyFile,
                         X509Certificate publicKey, PrivateKey privateKey,
                         OutputStream outputStream) {
            this.inputJar = inputJar;
            this.publicKeyFile = publicKeyFile;
            this.publicKey = publicKey;
            this.privateKey = privateKey;
            this.outputStream = outputStream;
            this.type = new ASN1ObjectIdentifier(CMSObjectIdentifiers.data.getId());
        }

        public Object getContent() {
            throw new UnsupportedOperationException();
        }

        public ASN1ObjectIdentifier getContentType() {
            return type;
        }

        public void write(OutputStream out) throws IOException {
            try {
                signer = new WholeFileSignerOutputStream(out, outputStream);
                JarOutputStream outputJar = new JarOutputStream(signer);

                Manifest manifest = addDigestsToManifest(inputJar);
                signFile(manifest, inputJar,
                         new X509Certificate[]{ publicKey },
                         new PrivateKey[]{ privateKey },
                         outputJar);
                // Assume the certificate is valid for at least an hour.
                long timestamp = publicKey.getNotBefore().getTime() + 3600L * 1000;
                addOtacert(outputJar, publicKeyFile, timestamp, manifest);

                signer.notifyClosing();
                outputJar.close();
                signer.finish();
            }
            catch (Exception e) {
                throw new IOException(e);
            }
        }

        public void writeSignatureBlock(ByteArrayOutputStream temp)
            throws IOException,
                   CertificateEncodingException,
                   OperatorCreationException,
                   CMSException {
            SignApk.writeSignatureBlock(this, publicKey, privateKey, temp);
        }

        public WholeFileSignerOutputStream getSigner() {
            return signer;
        }
    }

    private static void signWholeFile(JarFile inputJar, File publicKeyFile,
                                      X509Certificate publicKey, PrivateKey privateKey,
                                      OutputStream outputStream) throws Exception {
        CMSSigner cmsOut = new CMSSigner(inputJar, publicKeyFile,
                                         publicKey, privateKey, outputStream);

        ByteArrayOutputStream temp = new ByteArrayOutputStream();

        // put a readable message and a null char at the start of the
        // archive comment, so that tools that display the comment
        // (hopefully) show something sensible.
        // TODO: anything more useful we can put in this message?
        byte[] message = "signed by SignApk".getBytes("UTF-8");
        temp.write(message);
        temp.write(0);

        cmsOut.writeSignatureBlock(temp);

        byte[] zipData = cmsOut.getSigner().getTail();

        // For a zip with no archive comment, the
        // end-of-central-directory record will be 22 bytes long, so
        // we expect to find the EOCD marker 22 bytes from the end.
        if (zipData[zipData.length-22] != 0x50 ||
            zipData[zipData.length-21] != 0x4b ||
            zipData[zipData.length-20] != 0x05 ||
            zipData[zipData.length-19] != 0x06) {
            throw new IllegalArgumentException("zip data already has an archive comment");
        }

        int total_size = temp.size() + 6;
        if (total_size > 0xffff) {
            throw new IllegalArgumentException("signature is too big for ZIP file comment");
        }
        // signature starts this many bytes from the end of the file
        int signature_start = total_size - message.length - 1;
        temp.write(signature_start & 0xff);
        temp.write((signature_start >> 8) & 0xff);
        // Why the 0xff bytes?  In a zip file with no archive comment,
        // bytes [-6:-2] of the file are the little-endian offset from
        // the start of the file to the central directory.  So for the
        // two high bytes to be 0xff 0xff, the archive would have to
        // be nearly 4GB in size.  So it's unlikely that a real
        // commentless archive would have 0xffs here, and lets us tell
        // an old signed archive from a new one.
        temp.write(0xff);
        temp.write(0xff);
        temp.write(total_size & 0xff);
        temp.write((total_size >> 8) & 0xff);
        temp.flush();

        // Signature verification checks that the EOCD header is the
        // last such sequence in the file (to avoid minzip finding a
        // fake EOCD appended after the signature in its scan).  The
        // odds of producing this sequence by chance are very low, but
        // let's catch it here if it does.
        byte[] b = temp.toByteArray();
        for (int i = 0; i < b.length-3; ++i) {
            if (b[i] == 0x50 && b[i+1] == 0x4b && b[i+2] == 0x05 && b[i+3] == 0x06) {
                throw new IllegalArgumentException("found spurious EOCD header at " + i);
            }
        }

        outputStream.write(total_size & 0xff);
        outputStream.write((total_size >> 8) & 0xff);
        temp.writeTo(outputStream);
    }

    private static void signFile(Manifest manifest, JarFile inputJar,
                                 X509Certificate[] publicKey, PrivateKey[] privateKey,
                                 JarOutputStream outputJar)
        throws Exception {
        // Assume the certificate is valid for at least an hour.
        long timestamp = publicKey[0].getNotBefore().getTime() + 3600L * 1000;

        JarEntry je;

        // Everything else
        copyFiles(manifest, inputJar, outputJar, timestamp);

        // MANIFEST.MF
        je = new JarEntry(JarFile.MANIFEST_NAME);
        je.setTime(timestamp);
        outputJar.putNextEntry(je);
        manifest.write(outputJar);

        int numKeys = publicKey.length;
        for (int k = 0; k < numKeys; ++k) {
            // CERT.SF / CERT#.SF
            je = new JarEntry(numKeys == 1 ? CERT_SF_NAME :
                              String.format(CERT_SF_MULTI_NAME, k));
            je.setTime(timestamp);
            outputJar.putNextEntry(je);
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            writeSignatureFile(manifest, baos);
            byte[] signedData = baos.toByteArray();
            outputJar.write(signedData);

            // CERT.RSA / CERT#.RSA
            je = new JarEntry(numKeys == 1 ?
                              String.format(CERT_SIG_NAME, privateKey[k].getAlgorithm()) :
                              String.format(CERT_SIG_MULTI_NAME, k, "RSA"));
            je.setTime(timestamp);
            outputJar.putNextEntry(je);
            writeSignatureBlock(new CMSProcessableByteArray(signedData),
                                publicKey[k], privateKey[k], outputJar);
        }
    }

    private static void usage() {
        System.err.println("Usage: signapk [-w] " +
                           "publickey.x509[.pem] privatekey.pk8 " +
                           "[publickey2.x509[.pem] privatekey2.pk8 ...] " +
                           "input.jar output.jar");
        System.exit(2);
    }

    public static void main(String[] args) {
        if (args.length < 4) usage();

        sBouncyCastleProvider = new BouncyCastleProvider();
        Security.addProvider(sBouncyCastleProvider);

        boolean signWholeFile = false;
        int argstart = 0;
        while (args.length > argstart && args[argstart].charAt(0) == '-') {
            if (args[argstart].equals("-w")) {
                signWholeFile = true;
                argstart++;
            } else if (args[argstart].equalsIgnoreCase("-minsdk")) {
                try {
                    sMinSdkVersion = Integer.valueOf(args[++argstart]);
                } catch (NumberFormatException e) {
                    System.err.println("Invalid SDK version number: " + args[argstart]);
                    System.exit(2);
                }
                argstart++;
            } else {
                System.err.println("Invalid argument " + args[argstart]);
                usage();
                System.exit(2);
            }
        }

        if ((args.length - argstart) % 2 == 1) usage();
        int numKeys = ((args.length - argstart) / 2) - 1;
        if (signWholeFile && numKeys > 1) {
            System.err.println("Only one key may be used with -w.");
            System.exit(2);
        }

        String inputFilename = args[args.length-2];
        String outputFilename = args[args.length-1];

        JarFile inputJar = null;
        FileOutputStream outputFile = null;

        try {
            File firstPublicKeyFile = new File(args[argstart+0]);

            X509Certificate[] publicKey = new X509Certificate[numKeys];
            for (int i = 0; i < numKeys; ++i) {
                int argNum = argstart + i*2;
                publicKey[i] = readPublicKey(new File(args[argNum]));
            }

            // Set the ZIP file timestamp to the starting valid time
            // of the 0th certificate plus one hour (to match what
            // we've historically done).
            long timestamp = publicKey[0].getNotBefore().getTime() + 3600L * 1000;

            PrivateKey[] privateKey = new PrivateKey[numKeys];
            for (int i = 0; i < numKeys; ++i) {
                int argNum = argstart + i*2 + 1;
                privateKey[i] = readPrivateKey(new File(args[argNum]));
            }
            inputJar = new JarFile(new File(inputFilename), false);  // Don't verify.

            outputFile = new FileOutputStream(outputFilename);


            if (signWholeFile) {
                SignApk.signWholeFile(inputJar, firstPublicKeyFile,
                                      publicKey[0], privateKey[0], outputFile);
            } else {
                JarOutputStream outputJar = new JarOutputStream(outputFile);

                // For signing .apks, use the maximum compression to make
                // them as small as possible (since they live forever on
                // the system partition).  For OTA packages, use the
                // default compression level, which is much much faster
                // and produces output that is only a tiny bit larger
                // (~0.1% on full OTA packages I tested).
                outputJar.setLevel(9);

                signFile(addDigestsToManifest(inputJar), inputJar,
                         publicKey, privateKey, outputJar);
                outputJar.close();
            }
        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        } finally {
            try {
                if (inputJar != null) inputJar.close();
                if (outputFile != null) outputFile.close();
            } catch (IOException e) {
                e.printStackTrace();
                System.exit(1);
            }
        }
    }
}
