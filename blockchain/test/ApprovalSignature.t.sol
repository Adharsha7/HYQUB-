// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";

contract ApprovalSignatureTest is Test {
    address internal constant EXPECTED_SIGNER =
        0x11c1293F62eA90Bf1d27490Fd17DD77C8fAD0CDD;

    bytes32 internal constant PAYLOAD_HASH =
        0x9dd9761e440518dbc442e07c1d801a76113b735e3120cf6050e4bb2369ebccce;

    bytes internal constant BACKEND_SIGNATURE =
        hex"9d506eca818c088715137bb96d0443055a625466aa6006b90191c269c91f4ebb1f7a7228bbdda2e57b9d2c9dda86636f29c90731b75c743121c43d8eec1984181c";

    function recoverSigner(
        bytes32 payloadHash,
        bytes memory signature
    ) internal pure returns (address) {
        require(
            signature.length == 65,
            "invalid signature length"
        );

        bytes32 r;
        bytes32 s;
        uint8 v;

        assembly {
            r := mload(add(signature, 32))
            s := mload(add(signature, 64))
            v := byte(0, mload(add(signature, 96)))
        }

        if (v < 27) {
            v += 27;
        }

        bytes32 ethSignedMessageHash = keccak256(
            abi.encodePacked(
                "\x19Ethereum Signed Message:\n32",
                payloadHash
            )
        );

        return ecrecover(
            ethSignedMessageHash,
            v,
            r,
            s
        );
    }

    function test_recover_backend_signature() public {
        address recovered = recoverSigner(
            PAYLOAD_HASH,
            BACKEND_SIGNATURE
        );


        assertEq(
            recovered,
            EXPECTED_SIGNER
        );
    }

    function test_tampered_hash_rejected() public {
        bytes32 tamperedHash =
            0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;

        address recovered = recoverSigner(
            tamperedHash,
            BACKEND_SIGNATURE
        );

        assertTrue(
            recovered != EXPECTED_SIGNER
        );
    }

    function test_wrong_signature_rejected() public {
        bytes memory badSignature = BACKEND_SIGNATURE;

        badSignature[0] = bytes1(
            uint8(badSignature[0]) ^ 0x01
        );

        address recovered = recoverSigner(
            PAYLOAD_HASH,
            badSignature
        );

        assertTrue(
            recovered != EXPECTED_SIGNER
        );
    }
}
