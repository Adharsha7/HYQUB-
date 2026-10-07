// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";

contract ApprovalPayloadTest is Test {

    event DebugBytes(bytes data);

    function buildApprovalPayload()
        internal
        pure
        returns (bytes memory)
    {
        return abi.encode(
            "HYQUB_APPROVAL_V1",
            address(0x3333333333333333333333333333333333333333),
            bytes32(
                0xc3e8e51452336c1197934a2e42b8b41792d573d8084a136dfd1dfc654ca4b8bf
            ),
            uint256(2),
            uint256(1001),
            uint256(1000),
            _verifierIds()
        );
    }

    function _verifierIds()
        internal
        pure
        returns (string[] memory ids)
    {
        ids = new string[](2);

        ids[0] = "verifier-a";
        ids[1] = "verifier-b";
    }

    function test_python_approval_compatibility_vector()
        public
    {
        bytes memory encoded = buildApprovalPayload();

        bytes32 hash = sha256(encoded);

        emit log_named_uint(
            "ABI encoded bytes",
            encoded.length
        );

        emit log_named_bytes32(
            "Solidity approval hash",
            hash
        );

        // Debug output so we can compare Solidity ABI bytes
        // against the Python eth-abi output.
        emit DebugBytes(encoded);

        assertEq(
            hash,
            bytes32(
                0x9dd9761e440518dbc442e07c1d801a76113b735e3120cf6050e4bb2369ebccce
            )
        );
    }
}
