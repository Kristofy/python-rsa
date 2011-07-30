# -*- coding: utf-8 -*-
#
#  Copyright 2011 Sybren A. Stüvel <sybren@stuvel.eu>
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

'''RSA key generation code.

Create new keys with the newkeys() function. It will give you a PublicKey and a
PrivateKey object.

Loading and saving keys requires the pyasn1 module. This module is imported as
late as possible, such that other functionality will remain working in absence
of pyasn1.

'''

import abc
import logging

import rsa.prime
import rsa.pem
import rsa.common

log = logging.getLogger(__name__)

class AbstractKey(object):
    '''Abstract superclass for private and public keys.'''

    @classmethod
    def load_pkcs1(cls, keyfile, format='PEM'):
        r'''Loads a key in PKCS#1 DER or PEM format.

        @param keyfile: contents of a DER- or PEM-encoded file that contains
            the public key.
        @param format: the format of the file to load; 'PEM' or 'DER'
        @return: a PublicKey object
        '''

        methods = {
            'PEM': cls.load_pkcs1_pem,
            'DER': cls.load_pkcs1_der,
        }

        if format not in methods:
            formats = ', '.join(sorted(methods.keys()))
            raise ValueError('Unsupported format: %r, try one of %s' % (format,
                formats))

        method = methods[format]
        return method(keyfile)

    def save_pkcs1(self, format='PEM'):
        '''Saves the public key in PKCS#1 DER or PEM format.

        @param format: the format to save; 'PEM' or 'DER'
        @returns: the DER- or PEM-encoded public key.
        '''

        methods = {
            'PEM': self.save_pkcs1_pem,
            'DER': self.save_pkcs1_der,
        }

        if format not in methods:
            formats = ', '.join(sorted(methods.keys()))
            raise ValueError('Unsupported format: %r, try one of %s' % (format,
                formats))

        method = methods[format]
        return method()

class PublicKey(AbstractKey):
    '''Represents a public RSA key.

    This key is also known as the 'encryption key'. It contains the 'n' and 'e'
    values.

    Supports attributes as well as dictionary-like access.

    >>> PublicKey(5, 3)
    PublicKey(5, 3)

    >>> key = PublicKey(5, 3)
    >>> key.n
    5
    >>> key['n']
    5
    >>> key.e
    3
    >>> key['e']
    3

    '''

    __slots__ = ('n', 'e')

    def __init__(self, n, e):
        self.n = n
        self.e = e

    def __getitem__(self, key):
        return getattr(self, key)

    def __repr__(self):
        return u'PublicKey(%i, %i)' % (self.n, self.e)

    def __eq__(self, other):
        if other is None:
            return False

        if not isinstance(other, PublicKey):
            return False

        return self.n == other.n and self.e == other.e

    def __ne__(self, other):
        return not (self == other)

    @classmethod
    def load_pkcs1_der(cls, keyfile):
        r'''Loads a key in PKCS#1 DER format.

        @param keyfile: contents of a DER-encoded file that contains the public
            key.
        @return: a PublicKey object

        First let's construct a DER encoded key:

        >>> import base64
        >>> b64der = 'MAwCBQCNGmYtAgMBAAE='
        >>> der = base64.decodestring(b64der)

        This loads the file:

        >>> PublicKey.load_pkcs1_der(der)
        PublicKey(2367317549, 65537)

        '''

        from pyasn1.codec.der import decoder
        (priv, _) = decoder.decode(keyfile)

        # ASN.1 contents of DER encoded public key:
        #
        # RSAPublicKey ::= SEQUENCE {
        #     modulus           INTEGER,  -- n
        #     publicExponent    INTEGER,  -- e

        as_ints = tuple(int(x) for x in priv)
        return cls(*as_ints)

    def save_pkcs1_der(self):
        '''Saves the public key in PKCS#1 DER format.

        @returns: the DER-encoded public key.
        '''

        from pyasn1.type import univ, namedtype
        from pyasn1.codec.der import encoder

        class AsnPubKey(univ.Sequence):
            componentType = namedtype.NamedTypes(
                namedtype.NamedType('modulus', univ.Integer()),
                namedtype.NamedType('publicExponent', univ.Integer()),
            )

        # Create the ASN object
        asn_key = AsnPubKey()
        asn_key.setComponentByName('modulus', self.n)
        asn_key.setComponentByName('publicExponent', self.e)

        return encoder.encode(asn_key)

    @classmethod
    def load_pkcs1_pem(cls, keyfile):
        '''Loads a PKCS#1 PEM-encoded public key file.

        The contents of the file before the "-----BEGIN RSA PUBLIC KEY-----" and
        after the "-----END RSA PUBLIC KEY-----" lines is ignored.

        @param keyfile: contents of a PEM-encoded file that contains the public
            key.
        @return: a PublicKey object
        '''

        der = rsa.pem.load_pem(keyfile, 'RSA PUBLIC KEY')
        return cls.load_pkcs1_der(der)

    def save_pkcs1_pem(self):
        '''Saves a PKCS#1 PEM-encoded public key file.

        @return: contents of a PEM-encoded file that contains the public key.
        '''

        der = self.save_pkcs1_der()
        return rsa.pem.save_pem(der, 'RSA PUBLIC KEY')

class PrivateKey(AbstractKey):
    '''Represents a private RSA key.

    This key is also known as the 'decryption key'. It contains the 'n', 'e',
    'd', 'p', 'q' and other values.

    Supports attributes as well as dictionary-like access.

    >>> PrivateKey(3247, 65537, 833, 191, 17)
    PrivateKey(3247, 65537, 833, 191, 17)

    exp1, exp2 and coef don't have to be given, they will be calculated:

    >>> pk = PrivateKey(3727264081, 65537, 3349121513, 65063, 57287)
    >>> pk.exp1
    55063L
    >>> pk.exp2
    10095L
    >>> pk.coef
    50797L

    If you give exp1, exp2 or coef, they will be used as-is:

    >>> pk = PrivateKey(1, 2, 3, 4, 5, 6, 7, 8)
    >>> pk.exp1
    6
    >>> pk.exp2
    7
    >>> pk.coef
    8

    '''

    __slots__ = ('n', 'e', 'd', 'p', 'q', 'exp1', 'exp2', 'coef')

    def __init__(self, n, e, d, p, q, exp1=None, exp2=None, coef=None):
        self.n = n
        self.e = e
        self.d = d
        self.p = p
        self.q = q

        # Calculate the other values if they aren't supplied
        if exp1 is None:
            self.exp1 = long(d % (p - 1))
        else:
            self.exp1 = exp1

        if exp1 is None:
            self.exp2 = long(d % (q - 1))
        else:
            self.exp2 = exp2

        if coef is None:
            (_, self.coef, _) = extended_gcd(q, p)
        else:
            self.coef = coef

    def __getitem__(self, key):
        return getattr(self, key)

    def __repr__(self):
        return u'PrivateKey(%(n)i, %(e)i, %(d)i, %(p)i, %(q)i)' % self

    def __eq__(self, other):
        if other is None:
            return False

        if not isinstance(other, PrivateKey):
            return False

        return (self.n == other.n and
            self.e == other.e and
            self.d == other.d and
            self.p == other.p and
            self.q == other.q and
            self.exp1 == other.exp1 and
            self.exp2 == other.exp2 and
            self.coef == other.coef)

    def __ne__(self, other):
        return not (self == other)

    @classmethod
    def load_pkcs1_der(cls, keyfile):
        r'''Loads a key in PKCS#1 DER format.

        @param keyfile: contents of a DER-encoded file that contains the private
            key.
        @return: a PrivateKey object

        First let's construct a DER encoded key:

        >>> import base64
        >>> b64der = 'MC4CAQACBQDeKYlRAgMBAAECBQDHn4npAgMA/icCAwDfxwIDANcXAgInbwIDAMZt'
        >>> der = base64.decodestring(b64der)

        This loads the file:

        >>> PrivateKey.load_pkcs1_der(der)
        PrivateKey(3727264081, 65537, 3349121513, 65063, 57287)

        '''

        from pyasn1.codec.der import decoder
        (priv, _) = decoder.decode(keyfile)

        # ASN.1 contents of DER encoded private key:
        #
        # RSAPrivateKey ::= SEQUENCE {
        #     version           Version, 
        #     modulus           INTEGER,  -- n
        #     publicExponent    INTEGER,  -- e
        #     privateExponent   INTEGER,  -- d
        #     prime1            INTEGER,  -- p
        #     prime2            INTEGER,  -- q
        #     exponent1         INTEGER,  -- d mod (p-1)
        #     exponent2         INTEGER,  -- d mod (q-1) 
        #     coefficient       INTEGER,  -- (inverse of q) mod p
        #     otherPrimeInfos   OtherPrimeInfos OPTIONAL 
        # }

        if priv[0] != 0:
            raise ValueError('Unable to read this file, version %s != 0' % priv[0])

        as_ints = tuple(int(x) for x in priv[1:9])
        return cls(*as_ints)

    def save_pkcs1_der(self):
        '''Saves the private key in PKCS#1 DER format.

        @returns: the DER-encoded private key.
        '''

        from pyasn1.type import univ, namedtype
        from pyasn1.codec.der import encoder

        class AsnPrivKey(univ.Sequence):
            componentType = namedtype.NamedTypes(
                namedtype.NamedType('version', univ.Integer()),
                namedtype.NamedType('modulus', univ.Integer()),
                namedtype.NamedType('publicExponent', univ.Integer()),
                namedtype.NamedType('privateExponent', univ.Integer()),
                namedtype.NamedType('prime1', univ.Integer()),
                namedtype.NamedType('prime2', univ.Integer()),
                namedtype.NamedType('exponent1', univ.Integer()),
                namedtype.NamedType('exponent2', univ.Integer()),
                namedtype.NamedType('coefficient', univ.Integer()),
            )

        # Create the ASN object
        asn_key = AsnPrivKey()
        asn_key.setComponentByName('version', 0)
        asn_key.setComponentByName('modulus', self.n)
        asn_key.setComponentByName('publicExponent', self.e)
        asn_key.setComponentByName('privateExponent', self.d)
        asn_key.setComponentByName('prime1', self.p)
        asn_key.setComponentByName('prime2', self.q)
        asn_key.setComponentByName('exponent1', self.exp1)
        asn_key.setComponentByName('exponent2', self.exp2)
        asn_key.setComponentByName('coefficient', self.coef)

        return encoder.encode(asn_key)

    @classmethod
    def load_pkcs1_pem(cls, keyfile):
        '''Loads a PKCS#1 PEM-encoded private key file.

        The contents of the file before the "-----BEGIN RSA PRIVATE KEY-----" and
        after the "-----END RSA PRIVATE KEY-----" lines is ignored.

        @param keyfile: contents of a PEM-encoded file that contains the private
            key.
        @return: a PrivateKey object
        '''

        der = rsa.pem.load_pem(keyfile, 'RSA PRIVATE KEY')
        return cls.load_pkcs1_der(der)

    def save_pkcs1_pem(self):
        '''Saves a PKCS#1 PEM-encoded private key file.

        @return: contents of a PEM-encoded file that contains the private key.
        '''

        der = self.save_pkcs1_der()
        return rsa.pem.save_pem(der, 'RSA PRIVATE KEY')


def extended_gcd(a, b):
    """Returns a tuple (r, i, j) such that r = gcd(a, b) = ia + jb
    """
    # r = gcd(a,b) i = multiplicitive inverse of a mod b
    #      or      j = multiplicitive inverse of b mod a
    # Neg return values for i or j are made positive mod b or a respectively
    # Iterateive Version is faster and uses much less stack space
    x = 0
    y = 1
    lx = 1
    ly = 0
    oa = a                             #Remember original a/b to remove 
    ob = b                             #negative values from return results
    while b != 0:
        q = long(a // b)
        (a, b)  = (b, a % b)
        (x, lx) = ((lx - (q * x)),x)
        (y, ly) = ((ly - (q * y)),y)
    if (lx < 0): lx += ob              #If neg wrap modulo orignal b
    if (ly < 0): ly += oa              #If neg wrap modulo orignal a
    return (a, lx, ly)                 #Return only positive values

def find_p_q(nbits, accurate=True):
    ''''Returns a tuple of two different primes of nbits bits each.
    
    The resulting p * q has exacty 2 * nbits bits, and the returned p and q
    will not be equal.

    @param nbits: the number of bits in each of p and q.
    @param accurate: whether to enable accurate mode or not.
    @returns (p, q), where p > q

    >>> (p, q) = find_p_q(128)
    >>> from rsa import common
    >>> common.bit_size(p * q)
    256

    When not in accurate mode, the number of bits can be slightly less

    >>> (p, q) = find_p_q(128, accurate=False)
    >>> from rsa import common
    >>> common.bit_size(p * q) <= 256
    True
    >>> common.bit_size(p * q) > 240
    True
    
    '''
    
    total_bits = nbits * 2

    # Make sure that p and q aren't too close or the factoring programs can
    # factor n.
    shift = nbits // 16
    pbits = nbits + shift
    qbits = nbits - shift
    
    # Choose the two initial primes
    log.debug('find_p_q(%i): Finding p', nbits)
    p = rsa.prime.getprime(pbits)
    log.debug('find_p_q(%i): Finding q', nbits)
    q = rsa.prime.getprime(qbits)

    def is_acceptable(p, q):
        '''Returns True iff p and q are acceptable:
            
            - p and q differ
            - (p * q) has the right nr of bits (when accurate=True)
        '''

        if p == q:
            return False

        if not accurate:
            return True

        # Make sure we have just the right amount of bits
        found_size = rsa.common.bit_size(p * q)
        return total_bits == found_size

    # Keep choosing other primes until they match our requirements.
    change_p = False
    tries = 0
    while not is_acceptable(p, q):
        tries += 1
        # Change p on one iteration and q on the other
        if change_p:
            log.debug('   find another p')
            p = rsa.prime.getprime(pbits)
        else:
            log.debug('   find another q')
            q = rsa.prime.getprime(qbits)

        change_p = not change_p

    # We want p > q as described on
    # http://www.di-mgt.com.au/rsa_alg.html#crt
    return (max(p, q), min(p, q))

def calculate_keys(p, q, nbits):
    """Calculates an encryption and a decryption key given p and q, and
    returns them as a tuple (e, d)

    """

    phi_n = (p - 1) * (q - 1)

    # A very common choice for e is 65537
    e = 65537

    (divider, d, _) = extended_gcd(e, phi_n)

    if divider != 1:
        raise ValueError("e (%d) and phi_n (%d) are not relatively prime" %
                (e, phi_n))
    if (d < 0):
        raise ValueError("extended_gcd shouldn't return negative values, "
                "please file a bug")
    if (e * d) % phi_n != 1:
        raise ValueError("e (%d) and d (%d) are not mult. inv. modulo "
                "phi_n (%d)" % (e, d, phi_n))

    return (e, d)

def gen_keys(nbits, accurate=True):
    """Generate RSA keys of nbits bits. Returns (p, q, e, d).

    Note: this can take a long time, depending on the key size.
    
    @param nbits: the total number of bits in ``p`` and ``q``. Both ``p`` and
        ``q`` will use ``nbits/2`` bits.
    """

    (p, q) = find_p_q(nbits // 2, accurate)
    (e, d) = calculate_keys(p, q, nbits // 2)

    return (p, q, e, d)

def newkeys(nbits, accurate=True):
    """Generates public and private keys, and returns them as (pub, priv).

    The public key is also known as the 'encryption key', and is a PublicKey
    object. The private key is also known as the 'decryption key' and is a
    PrivateKey object.
    
    @param nbits: the number of bits required to store ``n = p*q``.
    @param accurate: when True, ``n`` will have exactly the number of bits you
        asked for. However, this makes key generation much slower.

    @return: a tuple (PublicKey, PrivateKey)
    
    """

    if nbits < 16:
        raise ValueError('Key too small')

    (p, q, e, d) = gen_keys(nbits)
    
    n = p * q

    return (
        PublicKey(n, e),
        PrivateKey(n, e, d, p, q)
    )

__all__ = ['PublicKey', 'PrivateKey', 'newkeys']

if __name__ == '__main__':
    import doctest
    
    try:
        for count in range(100):
            (failures, tests) = doctest.testmod()
            if failures:
                break

            if (count and count % 10 == 0) or count == 1:
                print '%i times' % count
    except KeyboardInterrupt:
        print 'Aborted'
    else:
        print 'Doctests done'
