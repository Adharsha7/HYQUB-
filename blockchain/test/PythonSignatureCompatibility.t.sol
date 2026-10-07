// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";

contract PythonSignatureCompatibilityTest is Test {

    function test_python_signature_recovers_expected_signer() public {
        bytes32 approvalHash =
            0x9dd9761e440518dbc442e07c1d801a76113b735e3120cf6050e4bb2369ebccce;

        bytes memory signature =
            hex"91f98369a795d0f5ad85a8f15e0ed9604b1f654f2f95e7e45325ebafcdbbc51826fa4d16ebbbb569880a3e0cc8fde0fcc6e7829c06eb216801ef8bbf11ef36ae1c";

        address expectedSigner =
            0xDBeC6b6D2e96687bF750Ed93C12135B445868E3A;

        bytes32 ethSignedMessageHash = keccak256(
            abi.encodePacked(
                "\x19Ethereum Signed Message:\n32",
                approvalHash
            )
        );

        require(
            signature.length == 65,
            "signature must be 65 bytes"
        );

        bytes32 r;
        bytes32 s;
        uint8 v;

        assembly {
            r := mload(add(signature, 32))
            s := mload(add(signature, 64))
            v := byte(0, mload(add(signature, 96)))
        }

        address recovered = ecrecover(
            ethSignedMessageHash,
            v,
            r,
            s
        );

        emit log_named_bytes32(
            "Approval hash",
            approvalHash
        );

        emit log_named_bytes32(
            "Ethereum signed message hash",
            ethSignedMessageHash
        );

        emit log_named_address(
            "Expected signer",
            expectedSigner
        );

        emit log_named_address(
            "Recovered signer",
            recovered
        );

        assertEq(
            recovered,
            expectedSigner
        );
    }
}
