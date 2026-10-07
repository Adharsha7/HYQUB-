// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";

contract TransactionIntentTest is Test {

    function buildTransactionIntent(
        uint256 chainId,
        address wallet,
        address target,
        uint256 value,
        bytes memory data,
        uint256 keyVersion
    ) internal pure returns (bytes memory) {

        return abi.encode(
            "HYQUB_TX_V1",
            chainId,
            wallet,
            target,
            value,
            data,
            keyVersion
        );
    }

    function test_python_compatibility_vector() public  {

        uint256 chainId = 31337;

        address wallet =
            0x3333333333333333333333333333333333333333;

        address target =
            0x4444444444444444444444444444444444444444;

        uint256 value = 1000000000000000;

        bytes memory data =
            hex"123456";

        uint256 keyVersion = 2;

        bytes memory encoded = buildTransactionIntent(
            chainId,
            wallet,
            target,
            value,
            data,
            keyVersion
        );

        bytes32 hash = sha256(encoded);

        emit log_named_uint(
            "Encoded bytes",
            encoded.length
        );

        emit log_named_bytes32(
            "Solidity hash",
            hash
        );

        assertEq(
            hash,
            bytes32(
                0xc3e8e51452336c1197934a2e42b8b41792d573d8084a136dfd1dfc654ca4b8bf
            )
        );
    }
}
